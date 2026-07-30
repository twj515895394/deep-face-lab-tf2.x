"""Ticket 16: WeightedIndexHost spawn / multi-child IPC tests.

Must use top-level worker targets so spawn can pickle them on Windows.
"""

from __future__ import annotations

import multiprocessing
import unittest

import numpy as np

from samplelib.sampling.weighted_index_host import (
    WeightedIndexHost,
    WeightedIndexHostConfig,
)


def _spawn_child_draw(client, count, out_queue):
    try:
        # After spawn, host_ref must be None and draw must still work via Queues/Events.
        if client._host_ref is not None:
            out_queue.put(("fail", "host_ref_not_none", type(client._host_ref).__name__))
            return
        indices = client.multi_get(count)
        out_queue.put(("ok", indices))
    except Exception as e:
        out_queue.put(("err", type(e).__name__, str(e)))


def _spawn_child_draw_with_tag(client, count, tag, out_queue):
    try:
        if client._host_ref is not None:
            out_queue.put((tag, "fail", "host_ref_not_none"))
            return
        indices = client.multi_get(count)
        out_queue.put((tag, "ok", indices))
    except Exception as e:
        out_queue.put((tag, "err", type(e).__name__, str(e)))


def _spawn_child_draw_after_signal(client, ready_event, go_event, out_queue):
    ready_event.set()
    go_event.wait(timeout=15)
    try:
        if client._host_ref is not None:
            out_queue.put(("fail", "host_ref_not_none"))
            return
        indices = client.multi_get(2)
        out_queue.put(("ok", indices))
    except Exception as e:
        out_queue.put(("err", type(e).__name__, str(e)))


class TestBatch2WeightedIndexHostSpawn(unittest.TestCase):
    def test_spawn_child_draw(self):
        host = WeightedIndexHost(
            np.array([0.25, 0.25, 0.25, 0.25], dtype=np.float64),
            config=WeightedIndexHostConfig(seed=11, cycle_size=64, request_timeout_sec=10.0),
        )
        cli = host.create_cli()
        ctx = multiprocessing.get_context("spawn")
        out_q = ctx.Queue()
        proc = ctx.Process(target=_spawn_child_draw, args=(cli, 5, out_q))
        try:
            proc.start()
            proc.join(timeout=30)
            self.assertEqual(proc.exitcode, 0, f"child exitcode={proc.exitcode}")
            result = out_q.get(timeout=5)
            self.assertEqual(result[0], "ok", result)
            indices = result[1]
            self.assertEqual(len(indices), 5)
            for idx in indices:
                self.assertIn(idx, [0, 1, 2, 3])
            stats = host.snapshot_stats()
            self.assertEqual(stats["total_draws"], 5)
        finally:
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=3)
            host.close()
            self.assertFalse(host.thread.is_alive())

    def test_multi_spawn_children_no_cross_talk(self):
        host = WeightedIndexHost(
            np.array([0.5, 0.5], dtype=np.float64),
            config=WeightedIndexHostConfig(seed=99, cycle_size=128, request_timeout_sec=15.0),
        )
        ctx = multiprocessing.get_context("spawn")
        out_q = ctx.Queue()
        procs = []
        child_count = 4
        draws_each = 6
        try:
            for i in range(child_count):
                cli = host.create_cli()
                p = ctx.Process(
                    target=_spawn_child_draw_with_tag,
                    args=(cli, draws_each, f"c{i}", out_q),
                )
                procs.append(p)
                p.start()

            results = {}
            for _ in range(child_count):
                item = out_q.get(timeout=30)
                tag = item[0]
                status = item[1]
                self.assertEqual(status, "ok", item)
                results[tag] = item[2]

            for p in procs:
                p.join(timeout=30)
                self.assertEqual(p.exitcode, 0)

            self.assertEqual(len(results), child_count)
            for tag, indices in results.items():
                self.assertEqual(len(indices), draws_each, tag)
                for idx in indices:
                    self.assertIn(idx, [0, 1])

            stats = host.snapshot_stats()
            self.assertEqual(stats["total_draws"], child_count * draws_each)
        finally:
            for p in procs:
                if p.is_alive():
                    p.terminate()
                    p.join(timeout=3)
            host.close()
            self.assertFalse(host.thread.is_alive())

    def test_close_makes_spawned_client_fail_fast(self):
        """
        Client is spawned while Host is still open (valid Queue handles),
        then Host closes; the child must fail fast via closed_event.
        """
        host = WeightedIndexHost(
            np.array([1.0], dtype=np.float64),
            config=WeightedIndexHostConfig(request_timeout_sec=2.0),
        )
        cli = host.create_cli()
        ctx = multiprocessing.get_context("spawn")
        ready = ctx.Event()
        go = ctx.Event()
        out_q = ctx.Queue()
        proc = ctx.Process(
            target=_spawn_child_draw_after_signal,
            args=(cli, ready, go, out_q),
        )
        try:
            proc.start()
            self.assertTrue(ready.wait(timeout=15))
            host.close()
            go.set()
            proc.join(timeout=15)
            self.assertEqual(proc.exitcode, 0, f"child exitcode={proc.exitcode}")
            result = out_q.get(timeout=5)
            self.assertEqual(result[0], "err", result)
            self.assertEqual(result[1], "RuntimeError")
            self.assertIn("closed", result[2].lower())
        finally:
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=3)
            host.close()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    unittest.main()
