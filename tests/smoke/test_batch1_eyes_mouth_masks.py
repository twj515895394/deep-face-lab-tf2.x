import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = REPO_ROOT / "models" / "Model_SAEHD" / "Model.py"


def load_model_module_with_stubs():
    module_name = "batch1_stubbed_saehd_model"
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


class EyesMouthMaskHelpersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model_module = load_model_module_with_stubs()

    def test_priority_disabled_accepts_three_outputs(self):
        samples = [
            np.zeros((2, 4, 4, 3), dtype=np.float32),
            np.ones((2, 4, 4, 3), dtype=np.float32),
            np.ones((2, 4, 4, 1), dtype=np.float32),
        ]

        unpacked = self.model_module._unpack_training_samples(
            samples,
            has_eyes_mouth=False,
            domain="src",
        )

        self.assertIs(samples[0], unpacked[0])
        self.assertIs(samples[1], unpacked[1])
        self.assertIs(samples[2], unpacked[2])
        self.assertIsNone(unpacked[3])

    def test_priority_enabled_accepts_four_outputs(self):
        samples = [
            np.zeros((2, 4, 4, 3), dtype=np.float32),
            np.ones((2, 4, 4, 3), dtype=np.float32),
            np.ones((2, 4, 4, 1), dtype=np.float32),
            np.full((2, 4, 4, 1), 0.5, dtype=np.float32),
        ]

        unpacked = self.model_module._unpack_training_samples(
            samples,
            has_eyes_mouth=True,
            domain="dst",
        )

        self.assertIs(samples[3], unpacked[3])

    def test_priority_enabled_rejects_missing_mask(self):
        samples = [
            np.zeros((2, 4, 4, 3), dtype=np.float32),
            np.ones((2, 4, 4, 3), dtype=np.float32),
            np.ones((2, 4, 4, 1), dtype=np.float32),
        ]

        with self.assertRaisesRegex(ValueError, "expected 4 outputs"):
            self.model_module._unpack_training_samples(
                samples,
                has_eyes_mouth=True,
                domain="src",
            )

    def test_priority_enabled_rejects_shape_mismatch(self):
        samples = [
            np.zeros((2, 4, 4, 3), dtype=np.float32),
            np.ones((2, 4, 4, 3), dtype=np.float32),
            np.ones((2, 4, 4, 1), dtype=np.float32),
            np.ones((2, 2, 2, 1), dtype=np.float32),
        ]

        with self.assertRaisesRegex(ValueError, "shape must match"):
            self.model_module._unpack_training_samples(
                samples,
                has_eyes_mouth=True,
                domain="dst",
            )

    def test_priority_enabled_rejects_non_finite_mask(self):
        full_mask = np.ones((2, 4, 4, 1), dtype=np.float32)
        eyes_mouth_mask = np.ones((2, 4, 4, 1), dtype=np.float32)
        eyes_mouth_mask[0, 0, 0, 0] = np.nan
        samples = [
            np.zeros((2, 4, 4, 3), dtype=np.float32),
            np.ones((2, 4, 4, 3), dtype=np.float32),
            full_mask,
            eyes_mouth_mask,
        ]

        with self.assertRaisesRegex(ValueError, "inf or nan"):
            self.model_module._unpack_training_samples(
                samples,
                has_eyes_mouth=True,
                domain="src",
            )

    def test_priority_enabled_rejects_unsafe_mask_dtype(self):
        samples = [
            np.zeros((2, 4, 4, 3), dtype=np.float32),
            np.ones((2, 4, 4, 3), dtype=np.float32),
            np.ones((2, 4, 4, 1), dtype=np.float32),
            np.full((2, 4, 4, 1), "bad", dtype=object),
        ]

        with self.assertRaisesRegex(ValueError, "cannot be safely"):
            self.model_module._unpack_training_samples(
                samples,
                has_eyes_mouth=True,
                domain="dst",
            )

    def test_feed_uses_real_masks_instead_of_zero_replacements(self):
        full_src_mask = np.ones((2, 4, 4, 1), dtype=np.float32)
        full_dst_mask = np.ones((2, 4, 4, 1), dtype=np.float32)
        src_em = np.full((2, 4, 4, 1), 0.25, dtype=np.float32)
        dst_em = np.full((2, 4, 4, 1), 0.75, dtype=np.float32)
        feed = {}

        result = self.model_module._add_eyes_mouth_masks_to_feed(
            feed,
            "src_placeholder",
            "dst_placeholder",
            full_src_mask,
            full_dst_mask,
            src_em,
            dst_em,
            has_eyes_mouth=True,
        )

        self.assertIs(feed, result)
        self.assertIs(src_em, feed["src_placeholder"])
        self.assertIs(dst_em, feed["dst_placeholder"])
        self.assertFalse(np.all(feed["src_placeholder"] == 0))
        self.assertFalse(np.all(feed["dst_placeholder"] == 0))

    def test_feed_skips_masks_when_priority_disabled(self):
        feed = {"base": object()}

        result = self.model_module._add_eyes_mouth_masks_to_feed(
            feed,
            "src_placeholder",
            "dst_placeholder",
            np.ones((1, 2, 2, 1), dtype=np.float32),
            np.ones((1, 2, 2, 1), dtype=np.float32),
            None,
            None,
            has_eyes_mouth=False,
        )

        self.assertIs(feed, result)
        self.assertNotIn("src_placeholder", feed)
        self.assertNotIn("dst_placeholder", feed)

    def test_train_iter_passes_real_masks_to_unified_train(self):
        src_em = np.full((2, 4, 4, 1), 0.25, dtype=np.float32)
        dst_em = np.full((2, 4, 4, 1), 0.75, dtype=np.float32)
        src_samples = [
            np.zeros((2, 4, 4, 3), dtype=np.float32),
            np.ones((2, 4, 4, 3), dtype=np.float32),
            np.ones((2, 4, 4, 1), dtype=np.float32),
            src_em,
        ]
        dst_samples = [
            np.zeros((2, 4, 4, 3), dtype=np.float32),
            np.ones((2, 4, 4, 3), dtype=np.float32),
            np.ones((2, 4, 4, 1), dtype=np.float32),
            dst_em,
        ]
        captured = {}
        model = object.__new__(self.model_module.SAEHDModel)
        model.get_iter = lambda: 1
        model.pretrain = False
        model.pretrain_just_disabled = False
        model.generate_next_samples = lambda: (src_samples, dst_samples)
        model._has_eyes_mouth = True
        model.loss_scale_var = None

        def unified_train(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return np.array([1.0], dtype=np.float32), np.array([2.0], dtype=np.float32)

        model.unified_train = unified_train

        result = self.model_module.SAEHDModel.onTrainOneIter(model)

        self.assertIs(src_em, captured["kwargs"]["target_srcm_em"])
        self.assertIs(dst_em, captured["kwargs"]["target_dstm_em"])
        self.assertEqual((("src_loss", 1.0), ("dst_loss", 2.0)), result)

    def test_numpy_priority_loss_has_nonzero_synthetic_contribution(self):
        target = np.zeros((1, 4, 4, 3), dtype=np.float32)
        prediction = np.zeros((1, 4, 4, 3), dtype=np.float32)
        eyes_mouth_mask = np.zeros((1, 4, 4, 1), dtype=np.float32)
        target[:, 1:3, 1:3, :] = 1.0
        eyes_mouth_mask[:, 1:3, 1:3, :] = 1.0

        priority_loss = np.mean(
            300 * np.abs(
                target * eyes_mouth_mask - prediction * eyes_mouth_mask
            ),
            axis=(1, 2, 3),
        )
        zero_mask_loss = np.mean(
            300 * np.abs(
                target * np.zeros_like(eyes_mouth_mask)
                - prediction * np.zeros_like(eyes_mouth_mask)
            ),
            axis=(1, 2, 3),
        )

        self.assertGreater(float(priority_loss[0]), 0.0)
        self.assertEqual(0.0, float(zero_mask_loss[0]))


if __name__ == "__main__":
    unittest.main()
