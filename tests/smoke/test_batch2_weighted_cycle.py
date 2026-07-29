import unittest
import numpy as np

from samplelib.sampling.weighted_index_host import WeightedCycleSampler, WeightedIndexHostConfig


class TestBatch2WeightedCycle(unittest.TestCase):

    def test_deterministic_seed(self):
        probs = np.array([0.5, 0.3, 0.2], dtype=np.float64)
        config1 = WeightedIndexHostConfig(seed=42, cycle_size=100)
        config2 = WeightedIndexHostConfig(seed=42, cycle_size=100)
        config3 = WeightedIndexHostConfig(seed=99, cycle_size=100)

        sampler1 = WeightedCycleSampler(probs, config=config1)
        sampler2 = WeightedCycleSampler(probs, config=config2)
        sampler3 = WeightedCycleSampler(probs, config=config3)

        draw1 = sampler1.draw(20)
        draw2 = sampler2.draw(20)
        draw3 = sampler3.draw(20)

        self.assertEqual(draw1, draw2)
        self.assertNotEqual(draw1, draw3)

    def test_distribution_tolerance(self):
        probs = np.array([0.7, 0.2, 0.1], dtype=np.float64)
        config = WeightedIndexHostConfig(seed=123, cycle_size=10000)
        sampler = WeightedCycleSampler(probs, config=config)

        total_draws = 50000
        draws = sampler.draw(total_draws)

        counts = np.bincount(draws, minlength=3)
        freqs = counts / float(total_draws)

        # Allow +/- 0.02 absolute tolerance for 50,000 draws
        for i in range(3):
            self.assertAlmostEqual(freqs[i], probs[i], delta=0.02)

    def test_boundary_cases(self):
        # Single element
        probs1 = np.array([1.0], dtype=np.float64)
        sampler1 = WeightedCycleSampler(probs1, config=WeightedIndexHostConfig(seed=1))
        self.assertEqual(sampler1.draw(5), [0, 0, 0, 0, 0])

        # N < batch_size
        probs2 = np.array([0.6, 0.4], dtype=np.float64)
        sampler2 = WeightedCycleSampler(probs2, config=WeightedIndexHostConfig(seed=2))
        res2 = sampler2.draw(4)
        self.assertEqual(len(res2), 4)

        # N >> batch_size
        probs3 = np.ones(500, dtype=np.float64) / 500.0
        sampler3 = WeightedCycleSampler(probs3, config=WeightedIndexHostConfig(seed=3))
        res3 = sampler3.draw(16)
        self.assertEqual(len(res3), 16)
        self.assertEqual(len(set(res3)), 16)  # High probability all 16 unique

    def test_invalid_probabilities(self):
        with self.assertRaises(ValueError):
            WeightedCycleSampler(np.array([], dtype=np.float64))

        with self.assertRaises(ValueError):
            WeightedCycleSampler(np.array([[0.5, 0.5]], dtype=np.float64))

        with self.assertRaises(ValueError):
            WeightedCycleSampler(np.array([0.5, np.nan], dtype=np.float64))

        with self.assertRaises(ValueError):
            WeightedCycleSampler(np.array([0.5, np.inf], dtype=np.float64))

        with self.assertRaises(ValueError):
            WeightedCycleSampler(np.array([-0.1, 1.1], dtype=np.float64))

        with self.assertRaises(ValueError):
            WeightedCycleSampler(np.array([0.0, 0.0], dtype=np.float64))

    def test_duplicate_retries_and_rollover(self):
        probs = np.array([0.99, 0.01], dtype=np.float64)
        config = WeightedIndexHostConfig(seed=42, cycle_size=10, duplicate_retry_limit=5)
        sampler = WeightedCycleSampler(probs, config=config)

        # Draw batch of size 2. Since 0 has 99% prob, sampler will attempt retries when duplicate 0 occurs.
        res = sampler.draw(2)
        self.assertEqual(len(res), 2)
        self.assertGreaterEqual(sampler.stats.total_draws, 2)
        self.assertGreater(sampler.stats.cycle_build_count, 0)


if __name__ == "__main__":
    unittest.main()
