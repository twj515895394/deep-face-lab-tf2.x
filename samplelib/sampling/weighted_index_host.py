import multiprocessing
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

from samplelib.sampling.stats import SamplingStats


@dataclass(frozen=True)
class WeightedIndexHostConfig:
    seed: Optional[int] = None
    cycle_size: Optional[int] = None
    duplicate_retry_limit: int = 16
    configured_max: int = 65536


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
    Compatible with mplib.IndexHost API.
    """

    def __init__(
        self,
        probabilities: np.ndarray,
        config: Optional[WeightedIndexHostConfig] = None,
        bucket_ids: Optional[np.ndarray] = None,
        quality_quantiles: Optional[np.ndarray] = None,
    ):
        self.sampler = WeightedCycleSampler(
            probabilities=probabilities,
            config=config,
            bucket_ids=bucket_ids,
            quality_quantiles=quality_quantiles,
        )
        self.sq = multiprocessing.Queue()
        self.cqs: List[multiprocessing.Queue] = []
        self._closed = False
        self._fatal_error: Optional[str] = None

        self.thread = threading.Thread(target=self.host_thread)
        self.thread.daemon = True
        self.thread.start()

    def host_thread(self) -> None:
        sq = self.sq
        while not self._closed:
            try:
                while not sq.empty():
                    msg = sq.get_nowait()
                    if not isinstance(msg, tuple) or len(msg) == 0:
                        continue

                    cmd = msg[0]
                    if cmd == "stop":
                        self._closed = True
                        break
                    elif cmd == "draw":
                        _, cq_id, count = msg
                        res = self.sampler.draw(count)
                        if cq_id < len(self.cqs):
                            self.cqs[cq_id].put(("OK", res))
                    elif cmd == "stats":
                        _, cq_id = msg
                        res = self.sampler.stats.snapshot().to_dict()
                        if cq_id < len(self.cqs):
                            self.cqs[cq_id].put(("OK", res))
            except Exception as e:
                self._fatal_error = str(e)
                self._closed = True
                break

            time.sleep(0.001)

    def create_cli(self) -> "WeightedIndexHostClient":
        cq = multiprocessing.Queue()
        self.cqs.append(cq)
        cq_id = len(self.cqs) - 1
        return WeightedIndexHostClient(self.sq, cq, cq_id, host_ref=self)

    def snapshot_stats(self) -> Dict[str, Any]:
        return self.sampler.stats.snapshot().to_dict()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            try:
                self.sq.put(("stop",))
            except Exception:
                pass
            if self.thread.is_alive():
                self.thread.join(timeout=1.0)

    # Disable pickling for multiprocessing safety
    def __getstate__(self) -> dict:
        return {}

    def __setstate__(self, d: dict) -> None:
        self.__dict__.update(d)


class WeightedIndexHostClient:
    """
    Client interface for processes to request sample indices from WeightedIndexHost.
    """

    def __init__(
        self,
        sq: multiprocessing.Queue,
        cq: multiprocessing.Queue,
        cq_id: int,
        host_ref: Optional[WeightedIndexHost] = None,
    ):
        self.sq = sq
        self.cq = cq
        self.cq_id = cq_id
        self._host_ref = host_ref

    def multi_get(self, count: int) -> List[int]:
        if self._host_ref and self._host_ref._fatal_error:
            raise RuntimeError(f"WeightedIndexHost thread error: {self._host_ref._fatal_error}")

        self.sq.put(("draw", self.cq_id, count))
        start_t = time.time()

        while True:
            if not self.cq.empty():
                status, payload = self.cq.get()
                if status == "OK":
                    return payload
                raise RuntimeError(f"WeightedIndexHost draw error: {payload}")

            if self._host_ref:
                if self._host_ref._fatal_error:
                    raise RuntimeError(f"WeightedIndexHost thread error: {self._host_ref._fatal_error}")
                if self._host_ref._closed:
                    raise RuntimeError("WeightedIndexHost has been closed.")

            if time.time() - start_t > 30.0:
                raise TimeoutError("WeightedIndexHost multi_get timed out after 30s.")

            time.sleep(0.001)

    def snapshot_stats(self) -> Dict[str, Any]:
        if self._host_ref and self._host_ref._fatal_error:
            raise RuntimeError(f"WeightedIndexHost thread error: {self._host_ref._fatal_error}")

        self.sq.put(("stats", self.cq_id))
        start_t = time.time()

        while True:
            if not self.cq.empty():
                status, payload = self.cq.get()
                if status == "OK":
                    return payload
                raise RuntimeError(f"WeightedIndexHost stats error: {payload}")

            if time.time() - start_t > 10.0:
                raise TimeoutError("WeightedIndexHost snapshot_stats timed out after 10s.")

            time.sleep(0.001)
