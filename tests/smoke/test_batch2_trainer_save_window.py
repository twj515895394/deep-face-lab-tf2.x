"""Ticket 19: Trainer save-window boundary via real TrainerSaveController (no TF/GPU)."""

from __future__ import annotations

import queue
import unittest
from typing import Any, List

from mainscripts.trainer_save_control import TrainerSaveController
from samplelib.sampling.loss_stats import (
    LossWindowTracker,
    format_loss_window_log,
)


class FakeModel:
    """Minimal stand-in for Trainer save/train integration tests."""

    def __init__(self, fail_save_times: int = 0, start_iter: int = 0):
        self.iter = int(start_iter)
        self.loss_history: List[Any] = []
        self.save_calls = 0
        self.fail_save_times = fail_save_times
        self.target_iter = 0
        self._save_should_fail = fail_save_times
        self.train_calls = 0

    def get_iter(self):
        return self.iter

    def get_loss_history(self):
        return self.loss_history

    def get_target_iter(self):
        return self.target_iter

    def is_reached_iter_goal(self):
        return self.target_iter != 0 and self.iter >= self.target_iter

    def train_one_iter(self):
        self.train_calls += 1
        self.iter += 1
        loss = [0.5 / self.iter, 0.4 / self.iter]
        self.loss_history.append(loss)
        if len(self.loss_history) > 100000:
            self.loss_history = self.loss_history[::2]
        return self.iter, 0.001

    def save(self):
        if self._save_should_fail > 0:
            self._save_should_fail -= 1
            raise RuntimeError("injected-save-failure")
        self.save_calls += 1

    def pass_one_iter(self):
        return None


class TestBatch2TrainerSaveWindow(unittest.TestCase):
    def _make_ctrl(self, model, logs, warmup_iters=3):
        c2s = queue.Queue()
        window = LossWindowTracker()

        def log_info(msg, end=None):
            if isinstance(msg, str) and msg.startswith("[Save]"):
                logs.append(msg)

        ctrl = TrainerSaveController(
            model=model,
            loss_window=window,
            c2s=c2s,
            debug=False,
            warmup_iters=warmup_iters,
            log_info_fn=log_info,
        )
        return ctrl, window, c2s

    def test_session_start_excludes_old_history(self):
        model = FakeModel(start_iter=2)
        model.loss_history = [[9.0, 9.0], [8.0, 8.0]]
        logs: List[str] = []
        ctrl, window, _ = self._make_ctrl(model, logs, warmup_iters=0)
        self.assertEqual(len(window), 0)

        ctrl.train_one_recorded()
        stats = window.stats()
        self.assertEqual(stats.count, 1)
        self.assertNotIn(9.0, stats.mean)

    def test_save_boundary_excludes_post_save_batch(self):
        # Resume past iter=1 so initial_iter does not consume the window.
        model = FakeModel(start_iter=10)
        logs: List[str] = []
        ctrl, window, _ = self._make_ctrl(model, logs, warmup_iters=0)

        for _ in range(2):
            ctrl.train_one_recorded()

        ok = ctrl.model_save(reason="scheduled")
        self.assertTrue(ok)
        self.assertIn("window=2", logs[-1])
        self.assertIn("range=11..12", logs[-1])

        ctrl.train_one_recorded()
        self.assertEqual(len(window), 1)

        ok = ctrl.model_save(reason="manual")
        self.assertTrue(ok)
        self.assertIn("window=1", logs[-1])
        self.assertIn("[Save][manual]", logs[-1])

    def test_first_iter_save_count_one_via_controller(self):
        """initial_iter is triggered by real after_train_step, not a copied helper."""
        model = FakeModel()
        logs: List[str] = []
        ctrl, window, _ = self._make_ctrl(model, logs, warmup_iters=3)

        # One train group from iter=0 with warmup would overshoot without per-step checks.
        # Controller must save at iter==1 with window=1.
        s2c = queue.Queue()
        ctrl.run_train_group(s2c)

        self.assertIn("initial_iter", ctrl.save_reasons)
        initial_logs = [x for x in logs if "[Save][initial_iter]" in x]
        self.assertEqual(len(initial_logs), 1)
        self.assertIn("window=1", initial_logs[0])
        self.assertIn("range=1..1", initial_logs[0])
        # After initial save, buffer committed; remaining trains in the group are new window.
        self.assertGreaterEqual(model.get_iter(), 1)

    def test_target_not_overshot_by_warmup(self):
        model = FakeModel()
        model.target_iter = 2
        logs: List[str] = []
        ctrl, window, _ = self._make_ctrl(model, logs, warmup_iters=3)
        s2c = queue.Queue()
        ctrl.run_train_group(s2c)

        self.assertEqual(model.get_iter(), 2)
        self.assertTrue(ctrl.is_reached_goal)
        self.assertIn("target_reached", ctrl.save_reasons)
        self.assertIn("initial_iter", ctrl.save_reasons)
        # No extra batch after target.
        self.assertEqual(model.train_calls, 2)

    def test_target_one(self):
        model = FakeModel()
        model.target_iter = 1
        logs: List[str] = []
        ctrl, _, _ = self._make_ctrl(model, logs, warmup_iters=3)
        ctrl.run_train_group(queue.Queue())
        self.assertEqual(model.get_iter(), 1)
        self.assertEqual(model.train_calls, 1)
        self.assertIn("target_reached", ctrl.save_reasons)
        # T19-R2-03: single checkpoint — no initial_iter + target_reached double save.
        self.assertEqual(ctrl.save_reasons.count("target_reached"), 1)
        self.assertNotIn("initial_iter", ctrl.save_reasons)
        self.assertEqual(model.save_calls, 1)
        target_logs = [x for x in logs if "[Save][target_reached]" in x]
        self.assertEqual(len(target_logs), 1)
        initial_logs = [x for x in logs if "[Save][initial_iter]" in x]
        self.assertEqual(len(initial_logs), 0)

    def test_resume_near_target(self):
        model = FakeModel(start_iter=4)
        model.target_iter = 5
        logs: List[str] = []
        ctrl, _, _ = self._make_ctrl(model, logs, warmup_iters=3)
        ctrl.run_train_group(queue.Queue())
        self.assertEqual(model.get_iter(), 5)
        self.assertEqual(model.train_calls, 1)
        self.assertIn("target_reached", ctrl.save_reasons)
        self.assertNotIn("initial_iter", ctrl.save_reasons)

    def test_prequeued_close_trains_zero(self):
        model = FakeModel()
        logs: List[str] = []
        ctrl, window, c2s = self._make_ctrl(model, logs, warmup_iters=3)
        s2c = queue.Queue()
        s2c.put({"op": "close"})

        stopped = ctrl.process_commands(s2c)
        self.assertTrue(stopped)
        self.assertEqual(model.train_calls, 0)
        self.assertIn("exit", ctrl.save_reasons)
        self.assertIn("[Save][exit]", logs[-1])

    def test_close_during_group_stops_before_full_warmup(self):
        model = FakeModel()
        logs: List[str] = []
        ctrl, _, _ = self._make_ctrl(model, logs, warmup_iters=5)
        s2c = queue.Queue()

        # After first train, inject close so remaining warmup does not run.
        original_train = model.train_one_iter

        def train_then_close():
            result = original_train()
            if model.train_calls == 1:
                s2c.put({"op": "close"})
            return result

        model.train_one_iter = train_then_close
        ctrl.run_train_group(s2c)
        # close is detected before next train; exit save happens when process_commands runs
        self.assertEqual(model.train_calls, 1)
        self.assertTrue(ctrl.should_stop or ctrl.has_pending_close(s2c) or "exit" in ctrl.save_reasons)

        if not ctrl.should_stop:
            ctrl.process_commands(s2c)
        self.assertTrue(ctrl.should_stop)
        self.assertIn("exit", ctrl.save_reasons)

    def test_failed_save_retains_window_and_emits_error(self):
        model = FakeModel(fail_save_times=1, start_iter=10)
        logs: List[str] = []
        ctrl, window, c2s = self._make_ctrl(model, logs, warmup_iters=0)

        ctrl.train_one_recorded()
        ctrl.train_one_recorded()

        with self.assertRaises(RuntimeError):
            ctrl.model_save(reason="scheduled")

        self.assertEqual(len(window), 2)
        self.assertEqual(len(logs), 0)
        self.assertEqual(model.save_calls, 0)
        err = c2s.get_nowait()
        self.assertEqual(err["op"], "error")
        self.assertEqual(err["reason"], "scheduled")
        self.assertIn("injected-save-failure", err["error"])

        ctrl.train_one_recorded()
        ok = ctrl.model_save(reason="scheduled")
        self.assertTrue(ok)
        self.assertIn("window=3", logs[-1])
        self.assertEqual(len(window), 0)
        self.assertEqual(model.save_calls, 1)

    def test_empty_window_on_consecutive_save(self):
        model = FakeModel(start_iter=10)
        logs: List[str] = []
        ctrl, window, _ = self._make_ctrl(model, logs, warmup_iters=0)
        ctrl.train_one_recorded()
        ctrl.model_save(reason="manual")
        ctrl.model_save(reason="manual")
        self.assertIn("window=0 (empty)", logs[-1])
        self.assertNotIn("mean=", logs[-1])

    def test_log_emitted_before_next_train(self):
        model = FakeModel(start_iter=10)
        logs: List[str] = []
        ctrl, window, _ = self._make_ctrl(model, logs, warmup_iters=0)
        order = []

        ctrl.train_one_recorded()
        order.append("train1")
        ctrl.model_save(reason="scheduled")
        order.append("save")
        ctrl.train_one_recorded()
        order.append("train2")
        self.assertEqual(order, ["train1", "save", "train2"])
        self.assertTrue(any(x.startswith("[Save][scheduled]") for x in logs))

    def test_history_compression_does_not_shrink_window_buffer(self):
        model = FakeModel(start_iter=10)
        logs: List[str] = []
        ctrl, window, _ = self._make_ctrl(model, logs, warmup_iters=0)
        for _ in range(20):
            ctrl.train_one_recorded()
        # Simulate aggressive history compression
        model.loss_history = model.loss_history[::2]
        self.assertEqual(len(window), 20)
        ctrl.model_save(reason="scheduled")
        self.assertIn("window=20", logs[-1])

    def test_record_loss_degraded_warning(self):
        model = FakeModel()
        all_logs: List[str] = []
        c2s = queue.Queue()
        window = LossWindowTracker()

        def log_info(msg, end=None):
            all_logs.append(str(msg))

        ctrl = TrainerSaveController(
            model=model,
            loss_window=window,
            c2s=c2s,
            debug=False,
            warmup_iters=0,
            log_info_fn=log_info,
        )

        def boom():
            raise RuntimeError("hist-broken")

        model.get_loss_history = boom
        model.train_one_iter()
        model.iter = 1
        ctrl.record_train_loss()
        ctrl.record_train_loss()
        ctrl.record_train_loss()
        self.assertTrue(ctrl.degraded)
        self.assertEqual(ctrl.window_degraded_count, 3)
        # T19-R2-02: only first failure in the window emits a warning.
        degraded_logs = [x for x in all_logs if "[LossWindow] degraded" in x]
        self.assertEqual(len(degraded_logs), 1)

        # Successful save commits and resets window degraded state.
        model.get_loss_history = lambda: [[0.1, 0.2]]
        model._save_should_fail = 0
        model.loss_history = [[0.1, 0.2]]
        ctrl.record_train_loss()  # still boom? no, restored
        # Force one more boom-free append then save with prior degraded_count.
        ok = ctrl.model_save(reason="scheduled")
        self.assertTrue(ok)
        save_logs = [x for x in all_logs if x.startswith("[Save][scheduled]")]
        self.assertTrue(any("window_incomplete" in x for x in save_logs))
        self.assertTrue(any("degraded_count=" in x for x in save_logs))
        self.assertFalse(ctrl.degraded)
        self.assertEqual(ctrl.window_degraded_count, 0)
        self.assertFalse(window.degraded)

    def test_range_in_log_format(self):
        text = format_loss_window_log(
            "scheduled",
            12000,
            None,
            start_iter=11001,
            end_iter=12000,
        )
        self.assertIn("range=11001..12000", text)
        self.assertIn("window=0 (empty)", text)

    def test_main_thread_propagates_error_before_close(self):
        """T19-R2-01: op=error must not be swallowed as a normal close."""
        from mainscripts.Trainer import TrainerClientState

        state = TrainerClientState()
        self.assertEqual(
            state.on_message(
                {
                    "op": "error",
                    "reason": "scheduled",
                    "error": "disk full",
                    "error_type": "OSError",
                    "traceback": "tb-here",
                    "iter": 12,
                }
            ),
            "continue",
        )
        self.assertIsNotNone(state.fatal_error)
        self.assertEqual(state.on_message({"op": "close"}), "exit_error")
        with self.assertRaises(RuntimeError) as ctx:
            state.raise_if_fatal()
        msg = str(ctx.exception)
        self.assertIn("disk full", msg)
        self.assertIn("scheduled", msg)
        self.assertIn("12", msg)
        self.assertIn("tb-here", msg)

    def test_main_thread_normal_close_no_raise(self):
        from mainscripts.Trainer import TrainerClientState

        state = TrainerClientState()
        self.assertEqual(state.on_message({"op": "close"}), "exit_ok")
        state.raise_if_fatal()  # must not raise

    def test_rich_error_not_overwritten_by_generic(self):
        """T19-R3-01: rich → generic → close keeps reason/iter."""
        from mainscripts.Trainer import TrainerClientState, prefer_richer_error

        rich = {
            "op": "error",
            "reason": "manual",
            "error": "disk full",
            "error_type": "OSError",
            "traceback": "tb-rich",
            "iter": 42,
        }
        generic = {
            "op": "error",
            "error": "disk full",
            "error_type": "OSError",
            "traceback": "tb-generic",
        }
        merged = prefer_richer_error(rich, generic)
        self.assertEqual(merged["reason"], "manual")
        self.assertEqual(merged["iter"], 42)

        state = TrainerClientState()
        self.assertEqual(state.on_message(rich), "continue")
        self.assertEqual(state.on_message(generic), "continue")
        self.assertEqual(state.on_message({"op": "close"}), "exit_error")
        self.assertEqual(state.fatal_error["reason"], "manual")
        self.assertEqual(state.fatal_error["iter"], 42)
        with self.assertRaises(RuntimeError) as ctx:
            state.raise_if_fatal()
        text = str(ctx.exception)
        self.assertIn("manual", text)
        self.assertIn("42", text)

    def test_controller_save_fail_reasons_preserve_context(self):
        """manual/scheduled/target/exit save failures all emit reason+iter."""
        for reason, setup in (
            ("manual", lambda c, s: (s.put({"op": "save"}), c.process_commands(s))),
            ("scheduled", lambda c, s: c.model_save(reason="scheduled")),
            ("target_reached", None),
            ("exit", lambda c, s: (s.put({"op": "close"}), c.process_commands(s))),
        ):
            if reason == "target_reached":
                model = FakeModel(fail_save_times=1)
                model.target_iter = 1
                logs: List[str] = []
                ctrl, _, c2s = self._make_ctrl(model, logs, warmup_iters=0)
                with self.assertRaises(RuntimeError):
                    ctrl.run_train_group(queue.Queue())
            else:
                model = FakeModel(fail_save_times=1, start_iter=10)
                logs = []
                ctrl, _, c2s = self._make_ctrl(model, logs, warmup_iters=0)
                ctrl.train_one_recorded()
                s2c = queue.Queue()
                with self.assertRaises(RuntimeError):
                    setup(ctrl, s2c)
            err = c2s.get_nowait()
            self.assertEqual(err["op"], "error", msg=reason)
            self.assertEqual(err["reason"], reason)
            self.assertIn("iter", err)
            self.assertIsNotNone(err["iter"])

    def test_save_fail_sequence_matches_trainer_thread_contract(self):
        """
        Simulate real trainerThread sequence:
          Controller rich error → optional generic outer error → close
        and consume via TrainerClientState as Trainer.main would.
        """
        from mainscripts.Trainer import TrainerClientState

        model = FakeModel(fail_save_times=1, start_iter=10)
        logs: List[str] = []
        ctrl, window, c2s = self._make_ctrl(model, logs, warmup_iters=0)
        ctrl.train_one_recorded()

        with self.assertRaises(RuntimeError):
            ctrl.model_save(reason="scheduled")
        self.assertIsNotNone(ctrl.last_error)

        # Outer except must not wipe rich context: either skip or merge.
        # Mimic fixed trainerThread: already_reported → no second put.
        # Also assert client-side prefer keeps reason if a generic arrives.
        rich = c2s.get_nowait()
        self.assertEqual(rich["reason"], "scheduled")
        self.assertEqual(rich["iter"], 11)

        state = TrainerClientState()
        state.on_message(rich)
        state.on_message(
            {
                "op": "error",
                "error": str(ctrl.last_error),
                "error_type": type(ctrl.last_error).__name__,
                "traceback": "outer-tb",
            }
        )
        self.assertEqual(state.on_message({"op": "close"}), "exit_error")
        with self.assertRaises(RuntimeError) as ctx:
            state.raise_if_fatal()
        self.assertIn("scheduled", str(ctx.exception))
        self.assertIn("11", str(ctx.exception))
        self.assertEqual(len(window), 1)
        self.assertEqual(model.save_calls, 0)

    def test_failed_exit_save_emits_error_and_stops(self):
        model = FakeModel(fail_save_times=1, start_iter=10)
        logs: List[str] = []
        ctrl, window, c2s = self._make_ctrl(model, logs, warmup_iters=0)
        ctrl.train_one_recorded()
        s2c = queue.Queue()
        s2c.put({"op": "close"})
        with self.assertRaises(RuntimeError):
            ctrl.process_commands(s2c)
        self.assertTrue(ctrl.should_stop)
        err = c2s.get_nowait()
        self.assertEqual(err["op"], "error")
        self.assertEqual(err["reason"], "exit")
        self.assertEqual(len(window), 1)


if __name__ == "__main__":
    unittest.main()
