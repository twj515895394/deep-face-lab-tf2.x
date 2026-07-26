import importlib.util
import ast
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = REPO_ROOT / "models" / "Model_SAEHD" / "Model.py"


def load_model_module_with_stubs():
    module_name = "batch1_stubbed_saehd_model_finite_gate"
    stubs = {
        "core": types.ModuleType("core"),
        "core.mathlib": types.ModuleType("core.mathlib"),
        "core.interact": types.ModuleType("core.interact"),
        "core.interact.interact": types.ModuleType("core.interact.interact"),
        "core.leras": types.ModuleType("core.leras"),
        "facelib": types.ModuleType("facelib"),
        "models": types.ModuleType("models"),
        "samplelib": types.ModuleType("samplelib"),
    }
    stubs["core"].mathlib = stubs["core.mathlib"]
    stubs["core.interact"].interact = stubs["core.interact.interact"]
    stubs["core.leras"].nn = types.SimpleNamespace()
    stubs["facelib"].FaceType = types.SimpleNamespace()
    stubs["models"].ModelBase = object

    with mock.patch.dict(sys.modules, stubs):
        spec = importlib.util.spec_from_file_location(module_name, MODEL_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


class FakeLossScale:
    def __init__(self, value):
        self.value = float(value)

    def assign(self, value):
        self.value = float(value)
        return ("assign", self.value)


class Batch1FiniteGradientGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model_module = load_model_module_with_stubs()

    def test_as_training_bool_accepts_numpy_true(self):
        self.assertTrue(self.model_module._as_training_bool(np.asarray(True)))

    def test_as_training_bool_rejects_numpy_false(self):
        self.assertFalse(self.model_module._as_training_bool(np.asarray(False)))

    def test_as_training_bool_defaults_for_none(self):
        self.assertFalse(self.model_module._as_training_bool(None, default=False))

    def test_unpack_legacy_train_result_defaults_to_applied(self):
        result = self.model_module._unpack_unified_train_result((np.asarray([1.0]), np.asarray([2.0])))
        self.assertTrue(result[2])
        self.assertTrue(result[3])

    def test_unpack_train_result_reads_gradient_flag(self):
        result = self.model_module._unpack_unified_train_result(
            (np.asarray([1.0]), np.asarray([2.0]), np.asarray(False))
        )
        self.assertFalse(result[2])
        self.assertFalse(result[3])

    def test_unpack_train_result_reads_step_flag(self):
        result = self.model_module._unpack_unified_train_result(
            (np.asarray([1.0]), np.asarray([2.0]), np.asarray(True), np.asarray(False))
        )
        self.assertTrue(result[2])
        self.assertFalse(result[3])

    def test_loss_scale_not_touched_when_absent(self):
        model = types.SimpleNamespace(loss_scale_var=None)
        self.model_module._update_loss_scale_state(model, gradients_finite=False)
        self.assertIsNone(model.loss_scale_var)

    def test_nonfinite_gradient_reduces_loss_scale_and_resets_counters(self):
        model = types.SimpleNamespace(
            loss_scale_var=FakeLossScale(32768.0),
            _loss_scale_consecutive_normal_steps=5,
            _loss_scale_steps_since_last_adjustment=5,
        )
        self.model_module.nn.tf_sess = types.SimpleNamespace(
            run=lambda value: value.value if isinstance(value, FakeLossScale) else value
        )

        self.model_module._update_loss_scale_state(model, gradients_finite=False)

        self.assertEqual(16384.0, model.loss_scale_var.value)
        self.assertEqual(0, model._loss_scale_consecutive_normal_steps)
        self.assertEqual(0, model._loss_scale_steps_since_last_adjustment)

    def test_finite_gradient_increments_loss_scale_counters(self):
        model = types.SimpleNamespace(
            loss_scale_var=FakeLossScale(32768.0),
            _loss_scale_consecutive_normal_steps=0,
            _loss_scale_steps_since_last_adjustment=0,
            _LOSS_SCALE_RECOVERY_INTERVAL=500,
            _LOSS_SCALE_MAX=65536,
        )

        self.model_module._update_loss_scale_state(model, gradients_finite=True)

        self.assertEqual(1, model._loss_scale_consecutive_normal_steps)
        self.assertEqual(1, model._loss_scale_steps_since_last_adjustment)
        self.assertEqual(32768.0, model.loss_scale_var.value)

    def test_finite_gradient_can_increase_loss_scale_at_recovery_interval(self):
        model = types.SimpleNamespace(
            loss_scale_var=FakeLossScale(32768.0),
            _loss_scale_consecutive_normal_steps=499,
            _loss_scale_steps_since_last_adjustment=499,
            _LOSS_SCALE_RECOVERY_INTERVAL=500,
            _LOSS_SCALE_MAX=65536,
        )
        self.model_module.nn.tf_sess = types.SimpleNamespace(
            run=lambda value: value.value if isinstance(value, FakeLossScale) else value
        )

        self.model_module._update_loss_scale_state(model, gradients_finite=True)

        self.assertEqual(65536.0, model.loss_scale_var.value)
        self.assertEqual(0, model._loss_scale_consecutive_normal_steps)

    def test_model_graph_uses_tf_cond_for_optimizer_gate(self):
        tree = ast.parse(MODEL_PATH.read_text(encoding="utf-8"))
        cond_calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "cond"
        ]

        self.assertTrue(cond_calls)

    def test_step_applied_is_derived_from_gated_update_results(self):
        source = MODEL_PATH.read_text(encoding="utf-8")

        self.assertIn("step_applied = tf.reduce_all(tf.stack(optimizer_update_ops))", source)


if __name__ == "__main__":
    unittest.main()
