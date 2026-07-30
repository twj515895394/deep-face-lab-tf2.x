"""
Ticket 19: extractable Trainer save / train control-flow helpers.

Keeps LossWindowTracker + model.save() freeze/commit semantics while making
initial/target/exit boundaries and command priority testable without TF/GPU.
"""

from __future__ import annotations

import queue
import traceback
from typing import Any, Callable, List, Optional, Sequence, Tuple


class TrainerSaveController:
    """
    Session-local save/train state machine used by trainerThread.

    Contracts:
    - process high-priority close/save commands before starting a train group
    - after every train_one_iter: record loss, check initial_iter / target
    - never train past target within a warmup group
    - save failure: do not commit window; surface structured error; re-raise
    """

    def __init__(
        self,
        model: Any,
        loss_window: Any,
        c2s: Any,
        *,
        debug: bool = False,
        warmup_iters: int = 3,
        log_fn: Optional[Callable[[str], None]] = None,
        log_info_fn: Optional[Callable[..., None]] = None,
    ):
        self.model = model
        self.loss_window = loss_window
        self.c2s = c2s
        self.debug = bool(debug)
        self.warmup_iters = max(0, int(warmup_iters))
        self.log_fn = log_fn
        self.log_info_fn = log_info_fn

        self.is_reached_goal = bool(model.is_reached_iter_goal())
        self.should_stop = False
        self.degraded = False
        self.window_degraded_count = 0
        self._degraded_warned_this_window = False
        self.last_error: Optional[BaseException] = None
        self.save_reasons: List[str] = []
        # Initial save only when session starts at iter 0 and first train reaches 1.
        self._initial_save_done = int(model.get_iter()) >= 1

    def _log(self, msg: str, **kwargs) -> None:
        if self.log_info_fn is not None:
            try:
                self.log_info_fn(msg, **kwargs)
                return
            except TypeError:
                self.log_info_fn(msg)
                return
        if self.log_fn is not None:
            self.log_fn(msg)

    def _reset_window_degraded(self) -> None:
        """Clear per-window degraded state after a successful commit."""
        self.degraded = False
        self.window_degraded_count = 0
        self._degraded_warned_this_window = False
        if hasattr(self.loss_window, "degraded"):
            try:
                self.loss_window.degraded = False
            except Exception:
                pass

    def record_train_loss(self) -> None:
        """Append latest train loss; mark degraded with bounded warning on failure."""
        try:
            iter_num = int(self.model.get_iter())
            self.loss_window.append_from_model_history(
                self.model.get_loss_history(),
                iter_num=iter_num,
            )
        except Exception as e:
            self.degraded = True
            self.window_degraded_count += 1
            if hasattr(self.loss_window, "degraded"):
                try:
                    self.loss_window.degraded = True
                except Exception:
                    pass
            # One warning per window; subsequent failures only increment the counter.
            if not self._degraded_warned_this_window:
                self._degraded_warned_this_window = True
                self._log(
                    f"[LossWindow] degraded: failed to record train loss "
                    f"({type(e).__name__}: {e}); further failures in this window "
                    f"are counted but not re-logged"
                )

    def model_save(self, reason: str = "scheduled") -> bool:
        """
        Freeze -> save -> log -> commit on success.
        On failure: keep buffer, put structured error on c2s, re-raise.
        """
        # After goal is reached, only exit may still run (empty window ok).
        if self.debug:
            return False
        if self.is_reached_goal and reason != "exit":
            return False

        from samplelib.sampling.loss_stats import format_loss_window_log

        frozen = self.loss_window.freeze()
        start_iter, end_iter = self.loss_window.iter_range_for_frozen(frozen)
        incomplete = bool(
            getattr(self.loss_window, "degraded", False)
            or self.degraded
            or self.window_degraded_count > 0
        )
        degraded_count = int(self.window_degraded_count)

        try:
            self._log("Saving....", end="\r")
        except TypeError:
            self._log("Saving....")

        try:
            self.model.save()
        except Exception as e:
            self.last_error = e
            tb = traceback.format_exc()
            try:
                self.c2s.put(
                    {
                        "op": "error",
                        "reason": reason,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "traceback": tb,
                        "iter": int(self.model.get_iter()),
                    }
                )
            except Exception:
                pass
            # Do not commit; buffer retained for retry.
            raise

        stats = self.loss_window.stats_for_frozen(frozen)
        try:
            log_line = format_loss_window_log(
                reason=reason,
                iter_num=self.model.get_iter(),
                stats=stats,
                start_iter=start_iter,
                end_iter=end_iter,
                window_incomplete=incomplete,
                degraded_count=degraded_count,
            )
            self._log(log_line)
        except Exception as log_exc:
            self._log(
                f"[Save][{reason}] iter={self.model.get_iter()} window={len(frozen)} "
                f"(stats log failed: {type(log_exc).__name__})"
            )

        self.loss_window.commit()
        self._reset_window_degraded()
        self.save_reasons.append(reason)
        return True

    def after_train_step(self) -> None:
        """Boundary checks that must run after every train_one_iter."""
        if self.debug or self.should_stop:
            return

        cur = int(self.model.get_iter())
        target = int(self.model.get_target_iter() or 0)
        reached = target != 0 and self.model.is_reached_iter_goal()

        # target=1 coincides with initial_iter: one checkpoint only (target_reached).
        if not self._initial_save_done and cur == 1:
            if reached and not self.is_reached_goal:
                self._log("Reached target iteration.")
                self.model_save(reason="target_reached")
                self._initial_save_done = True
                self.is_reached_goal = True
                self._log("You can use preview now.")
                return
            self.model_save(reason="initial_iter")
            self._initial_save_done = True

        if reached and not self.is_reached_goal:
            self._log("Reached target iteration.")
            self.model_save(reason="target_reached")
            self.is_reached_goal = True
            self._log("You can use preview now.")

    def train_one_recorded(self) -> Tuple[int, float]:
        """Train one iter, record loss, run boundary checks."""
        result = self.model.train_one_iter()
        if isinstance(result, tuple) and len(result) >= 2:
            iter_num, iter_time = result[0], float(result[1])
        else:
            iter_num, iter_time = self.model.get_iter(), 0.0
        self.record_train_loss()
        self.after_train_step()
        return int(iter_num), float(iter_time)

    def has_pending_close(self, s2c: Any) -> bool:
        """Non-destructive check for a queued close command."""
        try:
            items = list(getattr(s2c, "queue", []))
        except Exception:
            items = []
        # queue.Queue has no public peek; use temporary drain/restore when available.
        if items:
            return any(isinstance(x, dict) and x.get("op") == "close" for x in items)

        # Fallback: drain into temp list then put back (best-effort).
        buffered = []
        found = False
        try:
            while True:
                try:
                    msg = s2c.get_nowait()
                except queue.Empty:
                    break
                buffered.append(msg)
                if isinstance(msg, dict) and msg.get("op") == "close":
                    found = True
        finally:
            for msg in buffered:
                try:
                    s2c.put(msg)
                except Exception:
                    pass
        return found

    def process_commands(
        self,
        s2c: Any,
        *,
        on_manual_save_success: Optional[Callable[[], None]] = None,
        on_preview: Optional[Callable[[], None]] = None,
        on_backup: Optional[Callable[[], None]] = None,
    ) -> bool:
        """
        Process pending control commands.
        Returns True when the outer loop should stop (close handled).
        """
        while True:
            try:
                msg = s2c.get_nowait()
            except queue.Empty:
                break
            if not isinstance(msg, dict):
                continue
            op = msg.get("op")
            if op == "save":
                if self.model_save(reason="manual") and on_manual_save_success is not None:
                    on_manual_save_success()
            elif op == "backup":
                if on_backup is not None:
                    on_backup()
            elif op == "preview":
                if on_preview is not None:
                    on_preview()
            elif op == "close":
                # Exit: save current window without training extra batches.
                try:
                    self.model_save(reason="exit")
                except Exception:
                    # Structured error already emitted; still stop the loop.
                    self.should_stop = True
                    raise
                self.should_stop = True
                return True
        return self.should_stop

    def run_train_group(self, s2c: Any) -> Optional[Tuple[int, float]]:
        """
        Run warmup + one timed train, stopping early on target/close.

        Returns the last timed (iter, iter_time) when a timed step ran, else None.
        """
        if self.debug or self.is_reached_goal or self.should_stop:
            return None

        last_timed: Optional[Tuple[int, float]] = None
        total_steps = self.warmup_iters + 1
        for step in range(total_steps):
            # Stop before each train if close is already queued.
            if self.has_pending_close(s2c):
                self.process_commands(s2c)
                break
            if self.should_stop or self.is_reached_goal:
                break

            is_timed = step == total_steps - 1
            iter_num, iter_time = self.train_one_recorded()
            if is_timed:
                last_timed = (iter_num, iter_time)

            if self.should_stop or self.is_reached_goal:
                break

        return last_timed
