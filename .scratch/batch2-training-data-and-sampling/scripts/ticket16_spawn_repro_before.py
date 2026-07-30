"""Ticket 16 pre-fix spawn repro for WeightedIndexHostClient.

Run from repo root:
  set PYTHONPATH=.
  python .scratch/batch2-training-data-and-sampling/scripts/ticket16_spawn_repro_before.py
"""

from __future__ import annotations

import multiprocessing as mp
import traceback

import numpy as np


def child_draw(client, out_q):
    try:
        hr = client._host_ref
        info = {
            "host_ref_is_none": hr is None,
            "host_type": type(hr).__name__ if hr is not None else None,
            "attrs": sorted(getattr(hr, "__dict__", {}).keys()) if hr is not None else None,
            "has_fatal": hasattr(hr, "_fatal_error") if hr is not None else None,
        }
        try:
            res = client.multi_get(4)
            out_q.put(("ok", info, res))
        except Exception as e:
            out_q.put(("err", info, type(e).__name__, str(e), traceback.format_exc()))
    except Exception as e:
        out_q.put(("fatal", type(e).__name__, str(e), traceback.format_exc()))


def main():
    from samplelib.sampling.weighted_index_host import (
        WeightedIndexHost,
        WeightedIndexHostConfig,
    )

    mp.freeze_support()
    probs = np.array([0.5, 0.5], dtype=np.float64)
    host = WeightedIndexHost(probs, config=WeightedIndexHostConfig(seed=1, cycle_size=64))
    cli = host.create_cli()
    print("PRE: _host_ref", type(cli._host_ref).__name__)
    print("start_method", mp.get_start_method())

    ctx = mp.get_context("spawn")
    oq = ctx.Queue()
    p = ctx.Process(target=child_draw, args=(cli, oq))
    p.start()
    p.join(timeout=20)
    print("exitcode", p.exitcode)
    try:
        print("child result", oq.get(timeout=2))
    except Exception as e:
        print("child result EMPTY/timeout", type(e).__name__, e)
    if p.is_alive():
        p.terminate()
        p.join(timeout=2)
    try:
        host.close()
    except Exception as e:
        print("host.close error", e)


if __name__ == "__main__":
    main()
