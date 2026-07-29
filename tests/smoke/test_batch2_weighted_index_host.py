import unittest
import numpy as np

from samplelib.sampling.weighted_index_host import (
    WeightedIndexHost,
    WeightedIndexHostConfig,
)


class TestBatch2WeightedIndexHost(unittest.TestCase):

    def test_single_cli_draw(self):
        probs = np.array([0.4, 0.3, 0.3], dtype=np.float64)
        config = WeightedIndexHostConfig(seed=42, cycle_size=100)
        host = WeightedIndexHost(probs, config=config)
        cli = host.create_cli()

        try:
            indices = cli.multi_get(8)
            self.assertEqual(len(indices), 8)
            for idx in indices:
                self.assertIn(idx, [0, 1, 2])
        finally:
            host.close()

    def test_multi_cli_concurrent_draw(self):
        probs = np.array([0.5, 0.5], dtype=np.float64)
        config = WeightedIndexHostConfig(seed=123, cycle_size=500)
        host = WeightedIndexHost(probs, config=config)

        cli1 = host.create_cli()
        cli2 = host.create_cli()

        try:
            draw1 = cli1.multi_get(10)
            draw2 = cli2.multi_get(10)

            self.assertEqual(len(draw1), 10)
            self.assertEqual(len(draw2), 10)

            stats = host.snapshot_stats()
            self.assertEqual(stats["total_draws"], 20)
        finally:
            host.close()

    def test_snapshot_stats_via_client(self):
        probs = np.array([0.8, 0.2], dtype=np.float64)
        bucket_ids = np.array([0, 1], dtype=np.int32)
        host = WeightedIndexHost(probs, bucket_ids=bucket_ids)
        cli = host.create_cli()

        try:
            cli.multi_get(5)
            stats = cli.snapshot_stats()
            self.assertEqual(stats["total_draws"], 5)
            self.assertIsNotNone(stats["bucket_draw_counts"])
        finally:
            host.close()

    def test_host_close_behaviour(self):
        probs = np.array([1.0], dtype=np.float64)
        host = WeightedIndexHost(probs)
        cli = host.create_cli()

        host.close()
        with self.assertRaises((RuntimeError, TimeoutError)):
            cli.multi_get(4)


if __name__ == "__main__":
    unittest.main()
