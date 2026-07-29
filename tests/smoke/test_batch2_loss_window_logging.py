import math
import unittest
import numpy as np
from samplelib.sampling.loss_stats import LossWindowStats, compute_loss_window_stats


class TestLossWindowLogging(unittest.TestCase):

    def test_empty_and_out_of_bounds_history(self):
        self.assertIsNone(compute_loss_window_stats([]))
        self.assertIsNone(compute_loss_window_stats(None))
        self.assertIsNone(compute_loss_window_stats([0.5, 0.4], start_index=2))
        self.assertIsNone(compute_loss_window_stats([0.5, 0.4], start_index=10))

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
        # Existing session history of 2 items
        history = [
            [0.8, 0.8],
            [0.7, 0.7],
            # New window items:
            [0.4, 0.3],
            [0.2, 0.1],
        ]
        # Start at index 2 (simulating new session start or post-save window)
        stats = compute_loss_window_stats(history, start_index=2)
        self.assertIsNotNone(stats)
        self.assertEqual(stats.count, 2)
        self.assertAlmostEqual(stats.mean[0], 0.30, places=5)
        self.assertAlmostEqual(stats.mean[1], 0.20, places=5)
        self.assertEqual(stats.last, (0.2, 0.1))

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


if __name__ == "__main__":
    unittest.main()
