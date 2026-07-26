"""Batch 1 Ticket 09: training save/resume smoke.

macOS 测试使用纯 NumPy 轨迹验证保存、销毁、重载和继续 step 的一致性；
真实 SAEHD / TensorFlow / GPU 保存恢复仍需 Windows 环境补证。
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_PATH = REPO_ROOT / "core" / "leras" / "training_save_resume_smoke.py"


def _load_smoke_module():
    module_name = "batch1_training_save_resume_smoke"
    spec = importlib.util.spec_from_file_location(module_name, SMOKE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load module {module_name} from {SMOKE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class Batch1TrainingSaveResumeSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.smoke = _load_smoke_module()

    def test_adabelief_save_destroy_reload_resume_matches_continuous_step(self):
        report = self.smoke.run_training_save_resume_smoke(optimizer="adabelief")

        self.assertEqual("numpy_training_save_resume", report["mode"])
        self.assertEqual("adabelief", report["optimizer"])
        self.assertTrue(report["checkpoint"]["exists"])
        self.assertTrue(report["checkpoint"]["non_empty"])
        self.assertTrue(report["weight_changed_before_save"])
        self.assertTrue(report["weight_changed_after_resume"])
        self.assertEqual(2, report["model_iter_before_save"])
        self.assertEqual(2, report["model_iter_after_load"])
        self.assertEqual(3, report["model_iter_after_resume"])
        self.assertEqual(0.0, report["max_abs_reload_error"])
        self.assertEqual(0.0, report["max_abs_update_error"])
        self.assertEqual(["ms", "vs"], report["optimizer_slot_keys"])

    def test_rmsprop_optimizer_state_survives_resume(self):
        report = self.smoke.run_training_save_resume_smoke(optimizer="rmsprop")

        self.assertEqual(["acc"], report["optimizer_slot_keys"])
        self.assertEqual(2, report["optimizer_iterations_before_save"])
        self.assertEqual(2, report["optimizer_iterations_after_load"])
        self.assertEqual(3, report["optimizer_iterations_after_resume"])
        self.assertEqual(0.0, report["reload_errors"]["acc"])
        self.assertEqual(0.0, report["update_errors"]["acc"])

    def test_lion_v2_state_survives_resume_with_schema_marker(self):
        report = self.smoke.run_training_save_resume_smoke(optimizer="lion")

        self.assertEqual(["c"], report["optimizer_slot_keys"])
        self.assertEqual(0.0, report["reload_errors"]["c"])
        self.assertEqual(0.0, report["update_errors"]["c"])
        self.assertEqual(0.0, report["max_abs_update_error"])

    def test_legacy_options_without_enhancements_keep_all_enhancements_disabled(self):
        report = self.smoke.run_training_save_resume_smoke(
            legacy_options={"resolution": 64, "face_type": "f"}
        )

        self.assertFalse(report["legacy_options"]["has_enhancements_field"])
        self.assertFalse(report["legacy_options"]["training_enabled"])
        self.assertFalse(report["legacy_options"]["merge_enabled"])
        self.assertTrue(report["legacy_options"]["fallback_on_optional_error"])
        self.assertFalse(report["legacy_options"]["strict_validation"])
        self.assertEqual(report["legacy_options"], report["loaded_legacy_options"])
        self.assertFalse(report["loaded_legacy_options"]["has_enhancements_field"])

    def test_low_precision_paths_remain_blocked_or_experimental_on_macos(self):
        report = self.smoke.run_training_save_resume_smoke()

        self.assertIn(report["low_precision_status"]["fp16"], {"blocked", "experimental"})
        self.assertIn(report["low_precision_status"]["bf16"], {"blocked", "experimental"})
        self.assertEqual("validated", report["precision_contract"]["status"])
        self.assertTrue(report["macos_lightweight_only"])

    def test_checkpoint_can_be_written_to_declared_storage_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = self.smoke.run_training_save_resume_smoke(storage_dir=Path(tmpdir))
            checkpoint_path = Path(report["checkpoint"]["path"])

            self.assertEqual(Path(tmpdir), checkpoint_path.parent)
            self.assertTrue(checkpoint_path.exists())
            self.assertGreater(report["checkpoint"]["size_bytes"], 0)

    def test_all_optimizer_bundle_reports_required_windows_gpu_boundary(self):
        bundle = self.smoke.run_all_training_save_resume_smokes()

        self.assertEqual(["adabelief", "rmsprop", "lion"], bundle["optimizers"])
        self.assertEqual(0.0, bundle["max_abs_reload_error"])
        self.assertEqual(0.0, bundle["max_abs_update_error"])
        self.assertTrue(bundle["macos_lightweight_only"])
        self.assertGreaterEqual(len(bundle["windows_gpu_validation_required"]), 10)
        for item in bundle["reports"].values():
            self.assertTrue(item["windows_gpu_validation_required"])

    def test_missing_checkpoint_raises_file_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(FileNotFoundError):
                self.smoke.load_training_checkpoint(Path(tmpdir) / "missing.pkl")


if __name__ == "__main__":
    unittest.main()
