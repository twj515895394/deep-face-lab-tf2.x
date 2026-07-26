import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[2]
PRECISION_PATH = REPO_ROOT / "core" / "leras" / "precision_contract.py"


def load_precision_contract_module():
    module_name = "batch1_precision_contract_smoke"
    spec = importlib.util.spec_from_file_location(module_name, PRECISION_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class FakeVar:
    def __init__(self, dtype):
        self.dtype = dtype


class Batch1PrecisionContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pc = load_precision_contract_module()

    def test_normalize_precision_aliases(self):
        self.assertEqual("fp32", self.pc.normalize_precision_name("float32"))
        self.assertEqual("fp16", self.pc.normalize_precision_name("mixed_float16"))
        self.assertEqual("bf16", self.pc.normalize_precision_name("BF16"))
        self.assertIsNone(self.pc.normalize_precision_name("auto"))
        self.assertIsNone(self.pc.normalize_precision_name(None))

    def test_fp32_is_validated_baseline(self):
        report = self.pc.build_default_saehd_contract(
            "fp32",
            runtime_capabilities={"tensorflow_available": True},
        )

        self.assertEqual("fp32", report["requested_precision"])
        self.assertEqual("fp32", report["effective_precision"])
        self.assertEqual(self.pc.STATUS_VALIDATED, report["status"])
        self.assertEqual("float32", report["compute_dtype"])
        self.assertEqual(["float32"], report["optimizer_slot_dtypes"])
        self.assertEqual("none", report["loss_scale_mode"])
        self.assertEqual("missing", report["evidence"]["windows_gpu_evidence"])

    def test_fp16_and_bf16_remain_experimental(self):
        caps = {
            "tensorflow_available": True,
            "float16_dtype_available": True,
            "bfloat16_dtype_available": True,
        }
        fp16 = self.pc.build_default_saehd_contract("fp16", runtime_capabilities=caps)
        bf16 = self.pc.build_default_saehd_contract("bf16", runtime_capabilities=caps)

        self.assertEqual(self.pc.STATUS_EXPERIMENTAL, fp16["status"])
        self.assertEqual("float16", fp16["master_weight_dtype"])
        self.assertEqual("missing_dynamic_loss_scale", fp16["loss_scale_mode"])
        self.assertEqual(self.pc.STATUS_EXPERIMENTAL, bf16["status"])
        self.assertEqual("bfloat16", bf16["gradient_dtype"])
        self.assertEqual(32768.0, bf16["loss_scale_value"])

    def test_invalid_precision_falls_back_to_fp32(self):
        report = self.pc.build_default_saehd_contract(
            "auto",
            runtime_capabilities={"tensorflow_available": True},
        )

        self.assertEqual("auto", report["requested_precision"])
        self.assertIsNone(report["requested_precision_normalized"])
        self.assertEqual("fp32", report["effective_precision"])
        self.assertEqual("invalid_requested_precision", report["fallback_reason"])

    def test_blocked_low_precision_falls_back_to_fp32(self):
        report = self.pc.build_default_saehd_contract(
            "bf16",
            runtime_capabilities={
                "tensorflow_available": True,
                "bfloat16_dtype_available": False,
                "float16_dtype_available": True,
            },
        )

        self.assertEqual("bf16", report["requested_precision"])
        self.assertEqual("fp32", report["effective_precision"])
        self.assertEqual(self.pc.STATUS_BLOCKED, report["status"])
        self.assertEqual("bfloat16_dtype_unavailable", report["fallback_reason"])
        self.assertFalse(report["use_bf16"])

    def test_tensorflow_missing_blocks_fp16(self):
        report = self.pc.build_default_saehd_contract(
            "fp16",
            runtime_capabilities={
                "tensorflow_available": False,
                "float16_dtype_available": False,
            },
        )

        self.assertEqual("fp32", report["effective_precision"])
        self.assertEqual(self.pc.STATUS_BLOCKED, report["status"])
        self.assertEqual("float16_dtype_unavailable", report["fallback_reason"])

    def test_audit_collects_weight_gradient_slot_and_reload_dtype(self):
        contract = self.pc.resolve_precision_contract(
            "fp32",
            runtime_capabilities={"tensorflow_available": True},
        )
        optimizer = SimpleNamespace(ms=[FakeVar("float32")], vs=[FakeVar("float32")])
        report = self.pc.audit_precision_dtypes(
            contract,
            weights=[FakeVar("float32")],
            gradients=[FakeVar("float32")],
            optimizer=optimizer,
            placeholders=[FakeVar("float32")],
            save_file_dtype="float32",
            load_variable_dtype="float32",
            max_abs_reload_error=0.0,
        )

        self.assertEqual([], report["mismatches"])
        self.assertEqual(["float32"], report["observed"]["master_weight_dtypes"])
        self.assertEqual(["float32"], report["observed"]["optimizer_slot_dtypes_observed"])
        self.assertTrue(report["evidence"]["optimizer_roundtrip_verified"])
        self.assertEqual(1e-6, report["evidence"]["optimizer_roundtrip_error_tolerance"])

    def test_roundtrip_evidence_requires_error_within_tolerance(self):
        contract = self.pc.resolve_precision_contract(
            "fp32",
            runtime_capabilities={"tensorflow_available": False},
        )
        report = self.pc.audit_precision_dtypes(
            contract,
            max_abs_reload_error=0.01,
            roundtrip_error_tolerance=1e-6,
        )

        self.assertFalse(report["evidence"]["optimizer_roundtrip_verified"])
        self.assertIn("requested=fp32", report["summary"])

    def test_mismatch_downgrades_validated_report(self):
        contract = self.pc.resolve_precision_contract(
            "fp32",
            runtime_capabilities={"tensorflow_available": True},
        )
        report = self.pc.audit_precision_dtypes(
            contract,
            weights=[FakeVar("float16")],
            gradients=[FakeVar("float16")],
        )

        self.assertEqual(self.pc.STATUS_EXPERIMENTAL, report["status"])
        self.assertTrue(report["mismatches"])

    def test_target_contract_is_documented_but_not_claimed_done(self):
        report = self.pc.build_default_saehd_contract(
            "bf16",
            runtime_capabilities={
                "tensorflow_available": True,
                "bfloat16_dtype_available": True,
            },
        )

        target = report["target_master_weight_contract"]
        self.assertEqual("float32", target["master_weight_dtype"])
        self.assertEqual("target_not_implemented_in_batch1", target["status"])


if __name__ == "__main__":
    unittest.main()
