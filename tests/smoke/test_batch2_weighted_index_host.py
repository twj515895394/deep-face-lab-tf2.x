import multiprocessing
import time
import unittest

import numpy as np

from samplelib.sampling.weighted_index_host import (
    WeightedIndexHost,
    WeightedIndexHostClient,
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
        host = WeightedIndexHost(
            probs,
            config=WeightedIndexHostConfig(request_timeout_sec=1.0, stats_timeout_sec=1.0),
        )
        cli = host.create_cli()

        host.close()
        with self.assertRaises(RuntimeError):
            cli.multi_get(4)

        # close is idempotent
        host.close()

    def test_create_cli_after_close_rejected(self):
        host = WeightedIndexHost(np.array([1.0], dtype=np.float64))
        host.close()
        with self.assertRaises(RuntimeError):
            host.create_cli()

    def test_client_getstate_nulls_host_ref(self):
        host = WeightedIndexHost(np.array([0.5, 0.5], dtype=np.float64))
        cli = host.create_cli()
        try:
            self.assertIsNotNone(cli._host_ref)
            state = cli.__getstate__()
            self.assertIsNone(state["_host_ref"])
            self.assertIn("sq", state)
            self.assertIn("cq", state)
            self.assertIn("_closed_event", state)
            self.assertIn("_fatal_event", state)
        finally:
            host.close()

    def test_n_lt_batch_and_count_boundaries(self):
        host = WeightedIndexHost(
            np.array([1.0], dtype=np.float64),
            config=WeightedIndexHostConfig(seed=7, cycle_size=32),
        )
        cli = host.create_cli()
        try:
            self.assertEqual(cli.multi_get(0), [])
            with self.assertRaises(ValueError):
                cli.multi_get(-1)

            # N=1, batch>1: duplicates allowed, length exact
            res = cli.multi_get(4)
            self.assertEqual(len(res), 4)
            self.assertTrue(all(i == 0 for i in res))
            stats = host.snapshot_stats()
            self.assertEqual(stats["total_draws"], 4)
        finally:
            host.close()

    def test_request_id_rejects_stale_response(self):
        sq = multiprocessing.Queue()
        cq = multiprocessing.Queue()
        closed = multiprocessing.Event()
        fatal = multiprocessing.Event()
        cli = WeightedIndexHostClient(
            sq=sq,
            cq=cq,
            cq_id=0,
            closed_event=closed,
            fatal_event=fatal,
            request_timeout_sec=1.0,
            stats_timeout_sec=1.0,
            host_ref=None,
        )
        # Preload a stale response for request_id=1; real request will be id=1 after first next.
        # Force request counter so next id is 2, with stale id=1 still in queue.
        cli._request_id = 1
        cq.put(("OK", 1, [9, 9]))
        cq.put(("OK", 2, [3, 4]))

        # multi_get will use request_id=2 and must ignore stale id=1
        # But multi_get also puts to sq - drain is not needed for response matching.
        # We need host not involved: put will succeed, wait reads cq.
        # Race: multi_get puts draw request then waits. We already queued responses.
        res = cli.multi_get(2)
        self.assertEqual(res, [3, 4])

    def test_timeout_uses_configurable_short_timeout(self):
        sq = multiprocessing.Queue()
        cq = multiprocessing.Queue()
        closed = multiprocessing.Event()
        fatal = multiprocessing.Event()
        cli = WeightedIndexHostClient(
            sq=sq,
            cq=cq,
            cq_id=0,
            closed_event=closed,
            fatal_event=fatal,
            request_timeout_sec=0.25,
            stats_timeout_sec=0.25,
            host_ref=None,
        )
        t0 = time.monotonic()
        with self.assertRaises(TimeoutError):
            cli.multi_get(1)
        elapsed = time.monotonic() - t0
        self.assertLess(elapsed, 2.0)

    def test_fatal_draw_surfaces_runtime_error(self):
        host = WeightedIndexHost(
            np.array([0.5, 0.5], dtype=np.float64),
            config=WeightedIndexHostConfig(request_timeout_sec=2.0),
        )
        cli = host.create_cli()
        try:
            host._fail_next_draw = RuntimeError("injected-host-failure")
            with self.assertRaises(RuntimeError) as ctx:
                cli.multi_get(3)
            self.assertIn("injected-host-failure", str(ctx.exception))
            self.assertTrue(host._fatal_event.is_set())
            # host thread should exit after fatal
            host.thread.join(timeout=2.0)
            self.assertFalse(host.thread.is_alive())
        finally:
            host.close()


if __name__ == "__main__":
    unittest.main()
