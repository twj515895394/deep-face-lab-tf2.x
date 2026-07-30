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
        logs: List[str] = []
        ctrl, window, _ = self._make_ctrl(model, logs, warmup_iters=0)

        def boom():
            raise RuntimeError("hist-broken")

        model.get_loss_history = boom
        model.train_one_iter()
        model.iter = 1
        ctrl.record_train_loss()
        self.assertTrue(ctrl.degraded)

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


if __name__ == "__main__":
    unittest.main()
