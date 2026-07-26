"""Batch 1 Ticket 05: optimizer save/reload/next-step roundtrip audit.

macOS 当前通常缺 TensorFlow，因此本测试以与源码公式对齐的 NumPy 轻量路径为主，
记录 AdaBelief / RMSprop / Lion 的 slot dtype、reload 误差与下一步更新误差。
不在本测试中修改或“修复” Lion 公式。
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[2]
ROUNDTRIP_PATH = REPO_ROOT / "core" / "leras" / "optimizer_roundtrip.py"
PRECISION_PATH = REPO_ROOT / "core" / "leras" / "precision_contract.py"


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class FakeVar:
    def __init__(self, dtype):
        self.dtype = dtype


class Batch1OptimizerRoundtripTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rt = _load_module("batch1_optimizer_roundtrip_smoke", ROUNDTRIP_PATH)
        cls.pc = _load_module("batch1_precision_contract_for_roundtrip", PRECISION_PATH)

    def test_slot_dtype_snapshot_reads_real_leras_dict_attrs(self):
        optimizer = SimpleNamespace(
            iterations=FakeVar("int64"),
            ms_dict={"w:0": FakeVar("float32")},
            vs_dict={"w:0": FakeVar("float32")},
            c_dict={"w:0": FakeVar("float32")},
            accumulators_dict={"w:0": FakeVar("float32")},
        )
        snapshot = self.pc.collect_optimizer_slot_dtype_snapshot(optimizer)

        self.assertEqual(["int64"], snapshot["iterations"])
        self.assertEqual(["float32"], snapshot["ms_dict"])
        self.assertEqual(["float32"], snapshot["vs_dict"])
        self.assertEqual(["float32"], snapshot["c_dict"])
        self.assertEqual(["float32"], snapshot["accumulators_dict"])

    def test_adabelief_numpy_roundtrip_is_exact(self):
        report = self.rt.run_numpy_optimizer_roundtrip("adabelief")

        self.assertEqual("adabelief", report["optimizer"])
        self.assertEqual("numpy_lightweight", report["mode"])
        self.assertEqual("float32", report["dtype"])
        self.assertIn("ms_dict", report["optimizer_slot_dtypes"])
        self.assertIn("vs_dict", report["optimizer_slot_dtypes"])
        self.assertEqual(["float32"], report["optimizer_slot_dtypes"]["ms_dict"])
        self.assertEqual(["float32"], report["optimizer_slot_dtypes"]["vs_dict"])
        self.assertEqual(0.0, report["max_abs_reload_error"])
        self.assertEqual(0.0, report["max_abs_update_error"])
        self.assertTrue(report["precision_audit"]["evidence"]["optimizer_roundtrip_verified"])

    def test_rmsprop_numpy_roundtrip_is_exact(self):
        report = self.rt.run_numpy_optimizer_roundtrip("rmsprop")

        self.assertEqual("rmsprop", report["optimizer"])
        self.assertIn("accumulators_dict", report["optimizer_slot_dtypes"])
        self.assertEqual(["float32"], report["optimizer_slot_dtypes"]["accumulators_dict"])
        self.assertEqual(0.0, report["max_abs_reload_error"])
        self.assertEqual(0.0, report["max_abs_update_error"])
        self.assertEqual(0.0, report["update_errors"]["weight"])
        self.assertEqual(0.0, report["update_errors"]["acc"])

    def test_lion_numpy_roundtrip_is_exact_without_changing_formula(self):
        report = self.rt.run_numpy_optimizer_roundtrip("lion", lr=1e-4, beta_1=0.9, beta_2=0.99)

        self.assertEqual("lion", report["optimizer"])
        self.assertIn("c_dict", report["optimizer_slot_dtypes"])
        self.assertEqual(["float32"], report["optimizer_slot_dtypes"]["c_dict"])
        self.assertEqual(0.0, report["max_abs_reload_error"])
        self.assertEqual(0.0, report["max_abs_update_error"])
        self.assertEqual(
            "current_source_uses_beta1_only_for_c; beta2_not_applied_in_ticket_05",
            report["lion_formula_note"],
        )

        base = self.rt.run_numpy_optimizer_roundtrip("lion", beta_2=0.50)
        alt = self.rt.run_numpy_optimizer_roundtrip("lion", beta_2=0.99)
        self.assertEqual(0.0, self.rt._max_abs_error(base["continuous_final_weight"], alt["continuous_final_weight"]))
        self.assertEqual(
            0.0,
            self.rt._max_abs_error(
                base["continuous_final_state"]["c"],
                alt["continuous_final_state"]["c"],
            ),
        )

    def test_all_supported_optimizers_report_errors_and_slot_dtypes(self):
        bundle = self.rt.run_all_numpy_optimizer_roundtrips()

        self.assertEqual(["adabelief", "rmsprop", "lion"], bundle["optimizers"])
        self.assertEqual(0.0, bundle["max_abs_reload_error"])
        self.assertEqual(0.0, bundle["max_abs_update_error"])
        for name in bundle["optimizers"]:
            report = bundle["reports"][name]
            self.assertEqual(0.0, report["max_abs_reload_error"])
            self.assertEqual(0.0, report["max_abs_update_error"])
            self.assertTrue(report["optimizer_slot_dtypes"])
            self.assertIn("windows_gpu_validation_required", report)

    def test_serialize_deserialize_preserves_slots(self):
        import numpy as np

        weight = np.asarray([1.0, 2.0], dtype=np.float32)
        state = {
            "iterations": 3,
            "ms": np.asarray([0.1, -0.2], dtype=np.float32),
            "vs": np.asarray([0.3, 0.4], dtype=np.float32),
        }
        payload = self.rt.serialize_optimizer_state("adabelief", weight, state)
        loaded_w, loaded_state = self.rt.deserialize_optimizer_state(payload)

        self.assertEqual(0.0, self.rt._max_abs_error(weight, loaded_w))
        self.assertEqual(3, loaded_state["iterations"])
        self.assertEqual(0.0, self.rt._max_abs_error(state["ms"], loaded_state["ms"]))
        self.assertEqual(0.0, self.rt._max_abs_error(state["vs"], loaded_state["vs"]))
        self.assertEqual("float32", payload["slot_dtypes"]["ms"])
        self.assertEqual("float32", payload["slot_dtypes"]["vs"])


if __name__ == "__main__":
    unittest.main()
