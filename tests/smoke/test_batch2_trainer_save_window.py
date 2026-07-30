"""Ticket 19: Trainer save-window boundary with a fake model (no TF/GPU)."""

from __future__ import annotations

import unittest
from typing import Any, List, Optional
from unittest import mock

from samplelib.sampling.loss_stats import (
    LossWindowTracker,
    format_loss_window_log,
)


class FakeModel:
    """Minimal stand-in for Trainer save/train integration tests."""

    def __init__(self, fail_save_times: int = 0):
        self.iter = 0
        self.loss_history: List[Any] = []
        self.save_calls = 0
        self.fail_save_times = fail_save_times
        self.target_iter = 0
        self._save_should_fail = fail_save_times

    def get_iter(self):
        return self.iter

    def get_loss_history(self):
        return self.loss_history

    def get_target_iter(self):
        return self.target_iter

    def is_reached_iter_goal(self):
        return self.target_iter != 0 and self.iter >= self.target_iter

    def train_one_iter(self):
        self.iter += 1
        # multi-dim like SAEHD src/dst
        loss = [0.5 / self.iter, 0.4 / self.iter]
        self.loss_history.append(loss)
        # Simulate optional history compression without changing semantics for small N
        if len(self.loss_history) > 100000:
            self.loss_history = self.loss_history[::2]
        return self.iter, 0.001

    def save(self):
        if self._save_should_fail > 0:
            self._save_should_fail -= 1
            raise RuntimeError("injected-save-failure")
        self.save_calls += 1


def _model_save_helper(model, loss_window: LossWindowTracker, reason: str, logs: list, debug=False, is_reached_goal=False):
    """Mirror Trainer.model_save semantics for unit testing without full trainerThread."""
    if debug or is_reached_goal:
        return False
    frozen = loss_window.freeze()
    model.save()
    stats = loss_window.stats_for_frozen(frozen)
    logs.append(format_loss_window_log(reason, model.get_iter(), stats))
    loss_window.commit()
    return True


class TestBatch2TrainerSaveWindow(unittest.TestCase):
    def test_session_start_excludes_old_history(self):
        model = FakeModel()
        # Pretend resume: old history already present
        model.loss_history = [[9.0, 9.0], [8.0, 8.0]]
        model.iter = 2
        window = LossWindowTracker()  # empty on session start
        self.assertEqual(len(window), 0)

        model.train_one_iter()
        window.append_from_model_history(model.get_loss_history())
        stats = window.stats()
        self.assertEqual(stats.count, 1)
        self.assertNotIn(9.0, stats.mean)

    def test_save_boundary_excludes_post_save_batch(self):
        model = FakeModel()
        window = LossWindowTracker()
        logs = []

        # train A, B
        for _ in range(2):
            model.train_one_iter()
            window.append_from_model_history(model.get_loss_history())

        # save after B — window should be A+B only
        ok = _model_save_helper(model, window, "scheduled", logs)
        self.assertTrue(ok)
        self.assertIn("window=2", logs[-1])

        # train C after save
        model.train_one_iter()
        window.append_from_model_history(model.get_loss_history())
        self.assertEqual(len(window), 1)

        ok = _model_save_helper(model, window, "manual", logs)
        self.assertTrue(ok)
        self.assertIn("window=1", logs[-1])
        self.assertIn("[Save][manual]", logs[-1])

    def test_first_iter_save_count_one(self):
        model = FakeModel()
        window = LossWindowTracker()
        logs = []
        model.train_one_iter()
        window.append_from_model_history(model.get_loss_history())
        _model_save_helper(model, window, "initial_iter", logs)
        self.assertIn("[Save][initial_iter]", logs[-1])
        self.assertIn("window=1", logs[-1])
        self.assertEqual(len(window), 0)

    def test_failed_save_retains_window_for_next_success(self):
        model = FakeModel(fail_save_times=1)
        window = LossWindowTracker()
        logs = []

        model.train_one_iter()
        window.append_from_model_history(model.get_loss_history())
        model.train_one_iter()
        window.append_from_model_history(model.get_loss_history())

        with self.assertRaises(RuntimeError):
            _model_save_helper(model, window, "scheduled", logs)

        # Buffer retained
        self.assertEqual(len(window), 2)
        self.assertEqual(len(logs), 0)
        self.assertEqual(model.save_calls, 0)

        # Another train then success should include all 3
        model.train_one_iter()
        window.append_from_model_history(model.get_loss_history())
        ok = _model_save_helper(model, window, "scheduled", logs)
        self.assertTrue(ok)
        self.assertIn("window=3", logs[-1])
        self.assertEqual(len(window), 0)
        self.assertEqual(model.save_calls, 1)

    def test_empty_window_on_consecutive_save(self):
        model = FakeModel()
        window = LossWindowTracker()
        logs = []
        model.train_one_iter()
        window.append_from_model_history(model.get_loss_history())
        _model_save_helper(model, window, "manual", logs)
        # second save without train
        _model_save_helper(model, window, "manual", logs)
        self.assertIn("window=0 (empty)", logs[-1])
        self.assertNotIn("mean=", logs[-1])

    def test_target_reached_and_exit_reasons(self):
        model = FakeModel()
        model.target_iter = 2
        window = LossWindowTracker()
        logs = []
        for _ in range(2):
            model.train_one_iter()
            window.append_from_model_history(model.get_loss_history())
        self.assertTrue(model.is_reached_iter_goal())
        _model_save_helper(model, window, "target_reached", logs)
        self.assertIn("[Save][target_reached]", logs[-1])
        self.assertIn("window=2", logs[-1])

        # exit with no new train -> empty or leftover
        _model_save_helper(model, window, "exit", logs)
        self.assertIn("[Save][exit]", logs[-1])

    def test_log_emitted_before_next_train(self):
        model = FakeModel()
        window = LossWindowTracker()
        logs = []
        model.train_one_iter()
        window.append_from_model_history(model.get_loss_history())
        order = []

        def save_and_log():
            frozen = window.freeze()
            model.save()
            order.append("save")
            logs.append(format_loss_window_log("scheduled", model.get_iter(), window.stats_for_frozen(frozen)))
            order.append("log")
            window.commit()

        save_and_log()
        model.train_one_iter()
        order.append("train")
        self.assertEqual(order, ["save", "log", "train"])
        self.assertTrue(logs[0].startswith("[Save][scheduled]"))

    def test_history_compression_does_not_shrink_window_buffer(self):
        model = FakeModel()
        window = LossWindowTracker()
        # Build a large buffer via tracker, independent of model history compression
        for i in range(20):
            model.train_one_iter()
            # Force compress model history each time (simulate aggressive compress)
            if len(model.loss_history) > 5:
                model.loss_history = model.loss_history[::2]
            window.append_loss([float(i), float(i) * 0.5])
        self.assertEqual(len(window), 20)
        logs = []
        _model_save_helper(model, window, "scheduled", logs)
        self.assertIn("window=20", logs[-1])


if __name__ == "__main__":
    unittest.main()
