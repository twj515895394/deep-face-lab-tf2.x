import unittest

import numpy as np

from samplelib.sampling.loss_stats import (
    LossWindowStats,
    LossWindowTracker,
    compute_loss_window_stats,
    format_loss_window_log,
)


class TestLossWindowLogging(unittest.TestCase):

    def test_empty_and_out_of_bounds_history(self):
        self.assertIsNone(compute_loss_window_stats([]))
        self.assertIsNone(compute_loss_window_stats(None))
        self.assertIsNone(compute_loss_window_stats([0.5, 0.4], start_index=2))
        self.assertIsNone(compute_loss_window_stats([0.5, 0.4], start_index=10))
        # empty half-open window
        self.assertIsNone(compute_loss_window_stats([0.5, 0.4], start_index=1, end_index=1))

    def test_single_dimension_loss_history(self):
        history = [0.1, 0.2, 0.3, 0.4, 0.5]
        stats = compute_loss_window_stats(history, start_index=0)
        self.assertIsNotNone(stats)
        self.assertEqual(stats.count, 5)
        self.assertAlmostEqual(stats.mean[0], 0.3, places=5)
        self.assertAlmostEqual(stats.median[0], 0.3, places=5)
        self.assertAlmostEqual(stats.last[0], 0.5, places=5)
        self.assertAlmostEqual(stats.minimum[0], 0.1, places=5)
        self.assertAlmostEqual(stats.maximum[0], 0.5, places=5)

    def test_multi_dimension_loss_history(self):
        history = [
            [0.40, 0.30],
            [0.30, 0.20],
            [0.20, 0.10],
        ]
        stats = compute_loss_window_stats(history, start_index=0)
        self.assertIsNotNone(stats)
        self.assertEqual(stats.count, 3)
        self.assertAlmostEqual(stats.mean[0], 0.30, places=5)
        self.assertAlmostEqual(stats.mean[1], 0.20, places=5)
        self.assertEqual(stats.last, (0.20, 0.10))

    def test_window_slice_offset(self):
        history = [
            [0.8, 0.8],
            [0.7, 0.7],
            [0.4, 0.3],
            [0.2, 0.1],
        ]
        stats = compute_loss_window_stats(history, start_index=2)
        self.assertIsNotNone(stats)
        self.assertEqual(stats.count, 2)
        self.assertAlmostEqual(stats.mean[0], 0.30, places=5)
        self.assertAlmostEqual(stats.mean[1], 0.20, places=5)
        self.assertEqual(stats.last, (0.2, 0.1))

    def test_half_open_end_index(self):
        history = [0.1, 0.2, 0.3, 0.4]
        stats = compute_loss_window_stats(history, start_index=1, end_index=3)
        self.assertIsNotNone(stats)
        self.assertEqual(stats.count, 2)
        self.assertAlmostEqual(stats.mean[0], 0.25, places=5)
        self.assertAlmostEqual(stats.last[0], 0.3, places=5)
        # end=None equals full remaining
        full = compute_loss_window_stats(history, start_index=1, end_index=None)
        self.assertEqual(full.count, 3)

    def test_end_less_than_start_raises(self):
        with self.assertRaises(ValueError):
            compute_loss_window_stats([0.1, 0.2, 0.3], start_index=2, end_index=1)

    def test_non_finite_value_rejection(self):
        history = [0.4, float("nan"), 0.3]
        with self.assertRaises(ValueError):
            compute_loss_window_stats(history, start_index=0)

        history_inf = [0.4, float("inf")]
        with self.assertRaises(ValueError):
            compute_loss_window_stats(history_inf, start_index=0)

    def test_inconsistent_dimension_rejection(self):
        history = [[0.4, 0.3], [0.2]]
        with self.assertRaises(ValueError):
            compute_loss_window_stats(history, start_index=0)

    def test_one_item_mean_equals_last(self):
        stats = compute_loss_window_stats([[0.42, 0.11]], start_index=0)
        self.assertEqual(stats.count, 1)
        self.assertEqual(stats.mean, stats.median)
        self.assertEqual(stats.mean, stats.last)
        self.assertEqual(stats.minimum, stats.maximum)

    def test_tracker_freeze_commit_and_failed_retain(self):
        tracker = LossWindowTracker()
        # session start empty — old history not mixed
        self.assertEqual(len(tracker), 0)

        tracker.append_loss([0.5, 0.4])
        tracker.append_loss([0.3, 0.2])
        frozen = tracker.freeze()
        self.assertEqual(len(frozen), 2)
        stats = tracker.stats_for_frozen(frozen)
        self.assertEqual(stats.count, 2)
        self.assertAlmostEqual(stats.mean[0], 0.4, places=5)

        # failed save: do not commit
        self.assertEqual(len(tracker), 2)
        tracker.append_loss([0.1, 0.1])
        frozen2 = tracker.freeze()
        self.assertEqual(len(frozen2), 3)
        tracker.commit()
        self.assertEqual(len(tracker), 0)

        # consecutive save without training: empty
        empty_stats = tracker.stats()
        self.assertIsNone(empty_stats)

    def test_tracker_immune_to_history_compression(self):
        tracker = LossWindowTracker()
        fake_history = [[float(i), float(i) * 0.5] for i in range(10)]
        for item in fake_history:
            tracker.append_loss(item)
        # Simulate ModelBase compressing history
        compressed = fake_history[::2]
        self.assertEqual(len(compressed), 5)
        # Tracker still has full window
        stats = tracker.stats()
        self.assertEqual(stats.count, 10)
        self.assertAlmostEqual(stats.mean[0], np.mean(range(10)), places=5)

    def test_format_loss_window_log(self):
        stats = compute_loss_window_stats([[0.2, 0.1], [0.4, 0.3]], 0)
        text = format_loss_window_log("scheduled", 12000, stats)
        self.assertIn("[Save][scheduled]", text)
        self.assertIn("iter=12000", text)
        self.assertIn("window=2", text)
        self.assertIn("src mean=", text)
        self.assertIn("dst mean=", text)
        empty = format_loss_window_log("manual", 5, None)
        self.assertIn("window=0 (empty)", empty)
        self.assertNotIn("mean=", empty.split("\n")[0] if "\n" in empty else "")


if __name__ == "__main__":
    unittest.main()
