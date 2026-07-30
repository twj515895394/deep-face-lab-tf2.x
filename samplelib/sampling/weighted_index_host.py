import multiprocessing
import queue
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from samplelib.sampling.stats import SamplingStats


@dataclass(frozen=True)
class WeightedIndexHostConfig:
    seed: Optional[int] = None
    cycle_size: Optional[int] = None
    duplicate_retry_limit: int = 16
    configured_max: int = 65536
    # Client wait timeouts (seconds). Tests may lower these.
    request_timeout_sec: float = 30.0
    stats_timeout_sec: float = 10.0
    # Host request queue get timeout used to wake for stop/fatal checks.
    host_get_timeout_sec: float = 0.05
    thread_join_timeout_sec: float = 2.0


class WeightedCycleSampler:
    """
    Pure single-threaded weighted cycle sampler with finite probability validation,
    deterministic RNG, cycle pre-generation, batch duplicate retry limits,
    and non-blocking sampling statistics updates.
    """

    def __init__(
        self,
        probabilities: np.ndarray,
        config: Optional[WeightedIndexHostConfig] = None,
        bucket_ids: Optional[np.ndarray] = None,
        quality_quantiles: Optional[np.ndarray] = None,
    ):
        self.config = config or WeightedIndexHostConfig()
        self.probabilities = self._validate_and_normalize(probabilities)
        self.N = len(self.probabilities)

        self.bucket_ids = None
        if bucket_ids is not None:
            self.bucket_ids = np.asarray(bucket_ids, dtype=np.int32)
            if len(self.bucket_ids) != self.N:
                raise ValueError("bucket_ids length does not match probabilities length")

        self.quality_quantiles = None
        if quality_quantiles is not None:
            self.quality_quantiles = np.asarray(quality_quantiles, dtype=np.int32)
            if len(self.quality_quantiles) != self.N:
                raise ValueError("quality_quantiles length does not match probabilities length")

        self.rng = np.random.RandomState(self.config.seed)
        self.cycle_size = self._compute_cycle_size()
        self.cycle: Optional[np.ndarray] = None
        self.cycle_pos = 0

        self.stats = SamplingStats()
        if self.bucket_ids is not None:
            num_buckets = int(np.max(self.bucket_ids)) + 1 if self.N > 0 else 0
            num_buckets = max(num_buckets, 128)
            self.stats.bucket_draw_counts = np.zeros(num_buckets, dtype=np.int64)

        if self.quality_quantiles is not None:
            num_q = int(np.max(self.quality_quantiles)) + 1 if self.N > 0 else 0
            num_q = max(num_q, 10)
            self.stats.quality_quantile_draw_counts = np.zeros(num_q, dtype=np.int64)

    def _validate_and_normalize(self, probs: np.ndarray) -> np.ndarray:
        p = np.asarray(probs, dtype=np.float64)
        if p.ndim != 1:
            raise ValueError(f"Probabilities must be 1D array, got shape {p.shape}")
        if len(p) == 0:
            raise ValueError("Probabilities array cannot be empty")
        if not np.all(np.isfinite(p)):
            raise ValueError("Probabilities contains non-finite values (NaN or Inf)")
        if np.any(p < 0):
            raise ValueError("Probabilities contains negative values")

        total = np.sum(p)
        if total <= 0:
            raise ValueError("Sum of probabilities must be strictly greater than 0")

        return p / total

    def _compute_cycle_size(self) -> int:
        if self.config.cycle_size is not None and self.config.cycle_size > 0:
            return self.config.cycle_size
        return max(min(self.N, self.config.configured_max), 4096)

    def build_cycle(self) -> None:
        t0 = time.time()
        self.cycle = self.rng.choice(self.N, size=self.cycle_size, replace=True, p=self.probabilities)
        self.rng.shuffle(self.cycle)
        self.cycle_pos = 0
        self.stats.cycle_build_count += 1
        self.stats.cycle_build_seconds += time.time() - t0

    def _next_single(self) -> int:
        if self.cycle is None or self.cycle_pos >= len(self.cycle):
            self.build_cycle()
        val = int(self.cycle[self.cycle_pos])
        self.cycle_pos += 1
        return val

    def draw(self, count: int) -> List[int]:
        if count <= 0:
            return []

        result: List[int] = []
        retry_limit = self.config.duplicate_retry_limit

        for _ in range(count):
            candidate = self._next_single()
            if self.N >= count and candidate in result:
                retries = 0
                accepted = False
                while retries < retry_limit:
                    self.stats.duplicate_retries += 1
                    retries += 1
                    candidate = self._next_single()
                    if candidate not in result:
                        accepted = True
                        break
                if not accepted:
                    self.stats.accepted_duplicates += 1

            result.append(candidate)
            self.stats.total_draws += 1

            if self.stats.bucket_draw_counts is not None and self.bucket_ids is not None:
                b_id = self.bucket_ids[candidate]
                if 0 <= b_id < len(self.stats.bucket_draw_counts):
                    self.stats.bucket_draw_counts[b_id] += 1

            if (
                self.stats.quality_quantile_draw_counts is not None
                and self.quality_quantiles is not None
            ):
                q_id = self.quality_quantiles[candidate]
                if 0 <= q_id < len(self.stats.quality_quantile_draw_counts):
                    self.stats.quality_quantile_draw_counts[q_id] += 1

        return result


class WeightedIndexHost:
    """
    Multiprocessing Index Server providing weighted index draws for workers.

    Host ownership contract:
    - Host object and host thread live only in the training main process.
    - Workers hold WeightedIndexHostClient only (Queues + Events).
    - Client must never require a live Host Python object after spawn.
    """

    def __init__(
        self,
        probabilities: np.ndarray,
        config: Optional[WeightedIndexHostConfig] = None,
        bucket_ids: Optional[np.ndarray] = None,
        quality_quantiles: Optional[np.ndarray] = None,
    ):
        self.config = config or WeightedIndexHostConfig()
        self.sampler = WeightedCycleSampler(
            probabilities=probabilities,
            config=self.config,
            bucket_ids=bucket_ids,
            quality_quantiles=quality_quantiles,
        )
        self.sq = multiprocessing.Queue()
        self.cqs: List[multiprocessing.Queue] = []
        self._next_client_id = 0

        self._closed = False
        self._closing = False
        self._fatal_error: Optional[str] = None
        self._fatal_traceback: Optional[str] = None
        # Test hook: if set, next draw raises this exception inside host thread.
        self._fail_next_draw: Optional[BaseException] = None

        self._closed_event = multiprocessing.Event()
        self._fatal_event = multiprocessing.Event()
        self._state_lock = threading.Lock()
        self._sampler_lock = threading.Lock()

        self.thread = threading.Thread(
            target=self.host_thread,
            name="WeightedIndexHost",
            daemon=True,
        )
        self.thread.start()

    def _put_client_response(self, cq_id: int, message: Tuple[Any, ...]) -> None:
        if 0 <= cq_id < len(self.cqs):
            try:
                self.cqs[cq_id].put(message)
            except Exception:
                pass

    def _mark_fatal(self, exc: BaseException, tb: Optional[str] = None) -> None:
        if tb is None:
            tb = traceback.format_exc()
        self._fatal_error = f"{type(exc).__name__}: {exc}"
        self._fatal_traceback = tb
        self._fatal_event.set()
        try:
            print(f"WeightedIndexHost fatal:\n{tb}", file=sys.stderr)
        except Exception:
            pass

    def host_thread(self) -> None:
        sq = self.sq
        get_timeout = float(self.config.host_get_timeout_sec)

        while True:
            try:
                try:
                    msg = sq.get(timeout=get_timeout)
                except queue.Empty:
                    continue
                except Exception:
                    # Queue may be closed during shutdown; exit without fatal.
                    if self._closing or self._closed:
                        break
                    raise

                if not isinstance(msg, tuple) or len(msg) == 0:
                    continue

                cmd = msg[0]
                if cmd == "stop":
                    # Stop is fully consumed here; loop exits after this message.
                    break

                if cmd == "draw":
                    # ("draw", client_id, request_id, count)
                    if len(msg) != 4:
                        continue
                    _, cq_id, request_id, count = msg
                    try:
                        if self._fail_next_draw is not None:
                            injected = self._fail_next_draw
                            self._fail_next_draw = None
                            raise injected
                        with self._sampler_lock:
                            res = self.sampler.draw(int(count))
                        self._put_client_response(cq_id, ("OK", request_id, res))
                    except Exception as e:
                        tb = traceback.format_exc()
                        self._mark_fatal(e, tb)
                        self._put_client_response(
                            cq_id,
                            ("ERROR", request_id, type(e).__name__, str(e)),
                        )
                        break

                elif cmd == "stats":
                    # ("stats", client_id, request_id)
                    if len(msg) != 3:
                        continue
                    _, cq_id, request_id = msg
                    try:
                        with self._sampler_lock:
                            res = self.sampler.stats.snapshot().to_dict()
                        self._put_client_response(cq_id, ("OK", request_id, res))
                    except Exception as e:
                        tb = traceback.format_exc()
                        self._mark_fatal(e, tb)
                        self._put_client_response(
                            cq_id,
                            ("ERROR", request_id, type(e).__name__, str(e)),
                        )
                        break
            except Exception as e:
                if self._closing or self._closed:
                    break
                tb = traceback.format_exc()
                self._mark_fatal(e, tb)
                break

        # Host loop ended: ensure waiters can observe terminal state.
        self._closed = True
        self._closed_event.set()

    def create_cli(self) -> "WeightedIndexHostClient":
        with self._state_lock:
            if self._closed or self._closing or self._fatal_event.is_set():
                raise RuntimeError("WeightedIndexHost is closed; cannot create new client.")
            cq = multiprocessing.Queue()
            cq_id = self._next_client_id
            self._next_client_id += 1
            self.cqs.append(cq)
            return WeightedIndexHostClient(
                sq=self.sq,
                cq=cq,
                cq_id=cq_id,
                closed_event=self._closed_event,
                fatal_event=self._fatal_event,
                request_timeout_sec=float(self.config.request_timeout_sec),
                stats_timeout_sec=float(self.config.stats_timeout_sec),
                host_ref=self,
            )

    def snapshot_stats(self) -> Dict[str, Any]:
        with self._sampler_lock:
            return self.sampler.stats.snapshot().to_dict()

    def close(self) -> None:
        """
        Close order:
        1) mark closing
        2) send stop
        3) join host thread with timeout
        4) mark closed event (clients fail-fast)
        5) close queues best-effort
        Idempotent when the host thread has already exited.

        If the host thread is still alive after join timeout, queues are still
        closed so clients do not hang, but close() raises RuntimeError and the
        thread handle is retained. A subsequent close() retries join / raises
        again while the thread remains alive.
        """
        with self._state_lock:
            if self._closed and not self.thread.is_alive():
                return
            if self._closed and self.thread.is_alive():
                # Previous close already failed; retry join before raising again.
                pass
            already_closing = self._closing
            self._closing = True

        if not already_closing:
            try:
                self.sq.put(("stop",))
            except Exception:
                pass

        timed_out = False
        if self.thread.is_alive():
            self.thread.join(timeout=float(self.config.thread_join_timeout_sec))
            if self.thread.is_alive():
                timed_out = True
                try:
                    print(
                        "WeightedIndexHost: host thread did not exit within join timeout",
                        file=sys.stderr,
                    )
                except Exception:
                    pass

        self._closed = True
        self._closed_event.set()

        # Best-effort resource cleanup. Do not raise on already-closed queues.
        for q in list(self.cqs) + [self.sq]:
            try:
                q.close()
            except Exception:
                pass
            # Host request loop may be stuck; cancel feeder join to avoid hang.
            cancel = getattr(q, "cancel_join_thread", None)
            if callable(cancel):
                try:
                    cancel()
                    continue
                except Exception:
                    pass
            try:
                q.join_thread()
            except Exception:
                pass

        if timed_out:
            raise RuntimeError(
                "WeightedIndexHost: host thread did not exit within join timeout"
            )

    def __del__(self):
        # Safety net only; callers must still use close()/finalize() explicitly.
        # Never run full close() here: queue feeder teardown + stderr logging during
        # interpreter finalization can hard-crash Windows discover (shell exit != 0).
        try:
            is_finalizing = getattr(sys, "is_finalizing", None)
            if callable(is_finalizing) and is_finalizing():
                return
            self._closing = True
            self._closed = True
            if getattr(self, "_closed_event", None) is not None:
                try:
                    self._closed_event.set()
                except Exception:
                    pass
            th = getattr(self, "thread", None)
            if th is not None and getattr(th, "is_alive", lambda: False)():
                try:
                    self.sq.put(("stop",))
                except Exception:
                    pass
        except Exception:
            pass

    # Disable Host pickling across processes: only Client should travel to workers.
    def __getstate__(self) -> dict:
        return {}

    def __setstate__(self, d: dict) -> None:
        self.__dict__.update(d)


class WeightedIndexHostClient:
    """
    Client interface for worker processes to request sample indices.

    After spawn/pickle, ``_host_ref`` is always None. Closed/fatal state is
    observed via multiprocessing Events shared with the main-process Host.
    """

    def __init__(
        self,
        sq: multiprocessing.Queue,
        cq: multiprocessing.Queue,
        cq_id: int,
        closed_event: Optional[Any] = None,
        fatal_event: Optional[Any] = None,
        request_timeout_sec: float = 30.0,
        stats_timeout_sec: float = 10.0,
        host_ref: Optional[WeightedIndexHost] = None,
    ):
        self.sq = sq
        self.cq = cq
        self.cq_id = cq_id
        self._closed_event = closed_event
        self._fatal_event = fatal_event
        self.request_timeout_sec = float(request_timeout_sec)
        self.stats_timeout_sec = float(stats_timeout_sec)
        self._host_ref = host_ref
        self._request_id = 0

    def __getstate__(self) -> dict:
        state = self.__dict__.copy()
        # Host Python object must not cross process boundaries.
        state["_host_ref"] = None
        return state

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)
        if not hasattr(self, "_request_id"):
            self._request_id = 0

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _raise_if_terminal(self) -> None:
        if self._fatal_event is not None and self._fatal_event.is_set():
            detail = None
            if self._host_ref is not None:
                detail = getattr(self._host_ref, "_fatal_error", None)
            raise RuntimeError(
                f"WeightedIndexHost thread error: {detail or 'fatal event set'}"
            )

        if self._closed_event is not None and self._closed_event.is_set():
            raise RuntimeError("WeightedIndexHost has been closed.")

        # Same-process fallback when Events are unavailable (should be rare).
        host = self._host_ref
        if host is not None:
            fatal = getattr(host, "_fatal_error", None)
            if fatal:
                raise RuntimeError(f"WeightedIndexHost thread error: {fatal}")
            if getattr(host, "_closed", False) and not getattr(host, "_closing", False):
                raise RuntimeError("WeightedIndexHost has been closed.")

    def _wait_matched_response(
        self,
        request_id: int,
        timeout_sec: float,
        op_name: str,
    ) -> Any:
        start = time.monotonic()
        while True:
            self._raise_if_terminal()
            remaining = timeout_sec - (time.monotonic() - start)
            if remaining <= 0:
                self._raise_if_terminal()
                raise TimeoutError(
                    f"WeightedIndexHost {op_name} timed out after {timeout_sec}s."
                )
            try:
                msg = self.cq.get(timeout=min(0.1, remaining))
            except queue.Empty:
                continue

            if not isinstance(msg, tuple) or len(msg) < 2:
                continue

            status = msg[0]
            resp_id = msg[1]
            # Discard stale responses from timed-out or interleaved calls.
            if resp_id != request_id:
                continue

            if status == "OK":
                if len(msg) < 3:
                    raise RuntimeError(f"WeightedIndexHost {op_name} malformed OK response")
                return msg[2]

            if status == "ERROR":
                error_type = msg[2] if len(msg) > 2 else "RuntimeError"
                error_message = msg[3] if len(msg) > 3 else "unknown"
                if error_type == "TimeoutError":
                    raise TimeoutError(error_message)
                raise RuntimeError(
                    f"WeightedIndexHost {op_name} error: {error_message}"
                )

            raise RuntimeError(
                f"WeightedIndexHost {op_name} unexpected status: {status!r}"
            )

    def multi_get(self, count: int) -> List[int]:
        if count is None:
            raise ValueError("count must be an integer")
        count = int(count)
        if count < 0:
            raise ValueError("count must be >= 0")
        if count == 0:
            return []

        self._raise_if_terminal()
        request_id = self._next_request_id()
        try:
            self.sq.put(("draw", self.cq_id, request_id, count))
        except Exception as e:
            self._raise_if_terminal()
            raise RuntimeError(f"WeightedIndexHost draw enqueue failed: {e}") from e

        payload = self._wait_matched_response(
            request_id=request_id,
            timeout_sec=self.request_timeout_sec,
            op_name="multi_get",
        )
        if not isinstance(payload, list):
            raise RuntimeError("WeightedIndexHost multi_get returned non-list payload")
        return payload

    def snapshot_stats(self) -> Dict[str, Any]:
        self._raise_if_terminal()
        request_id = self._next_request_id()
        try:
            self.sq.put(("stats", self.cq_id, request_id))
        except Exception as e:
            self._raise_if_terminal()
            raise RuntimeError(f"WeightedIndexHost stats enqueue failed: {e}") from e

        payload = self._wait_matched_response(
            request_id=request_id,
            timeout_sec=self.stats_timeout_sec,
            op_name="snapshot_stats",
        )
        if not isinstance(payload, dict):
            raise RuntimeError("WeightedIndexHost snapshot_stats returned non-dict payload")
        return payload
