import math
import unittest

from samplelib.sampling.config import SamplingConfig, SamplingMode


class TestBatch2SamplingConfig(unittest.TestCase):
    def test_default_config(self):
        cfg = SamplingConfig()
        self.assertEqual(cfg.mode, SamplingMode.LEGACY)
        self.assertEqual(cfg.fallback_mode, SamplingMode.LEGACY_RANDOM)
        self.assertEqual(cfg.pose_balance_strength, 0.5)
        self.assertEqual(cfg.quality_strength, 0.5)
        self.assertEqual(cfg.uniform_mix, 0.1)
        self.assertEqual(cfg.min_sample_weight, 0.5)
        self.assertEqual(cfg.max_sample_weight, 2.0)

    def test_from_mapping_valid(self):
        mapping = {
            "mode": "pose_balanced",
            "fallback_mode": "legacy_uniform_yaw",
            "pose_balance_strength": 0.8,
            "quality_strength": 0.2,
            "min_sample_weight": 0.3,
            "max_sample_weight": 3.0,
            "seed": 42,
        }
        cfg = SamplingConfig.from_mapping(mapping)
        self.assertEqual(cfg.mode, SamplingMode.POSE_BALANCED)
        self.assertEqual(cfg.fallback_mode, SamplingMode.LEGACY_UNIFORM_YAW)
        self.assertEqual(cfg.pose_balance_strength, 0.8)
        self.assertEqual(cfg.quality_strength, 0.2)
        self.assertEqual(cfg.min_sample_weight, 0.3)
        self.assertEqual(cfg.max_sample_weight, 3.0)
        self.assertEqual(cfg.seed, 42)

    def test_invalid_nan_inf_values(self):
        mapping = {
            "mode": "invalid_mode_name",
            "fallback_mode": "invalid_fallback",
            "pose_balance_strength": float("nan"),
            "quality_strength": float("inf"),
            "min_sample_weight": 5.0,
            "max_sample_weight": 1.0,  # Invalid: min > max
        }
        cfg = SamplingConfig.from_mapping(mapping)
        self.assertEqual(cfg.mode, SamplingMode.LEGACY)
        self.assertEqual(cfg.fallback_mode, SamplingMode.LEGACY_RANDOM)
        self.assertEqual(cfg.pose_balance_strength, 0.5)
        self.assertEqual(cfg.quality_strength, 0.5)
        self.assertEqual(cfg.min_sample_weight, 0.5)
        self.assertEqual(cfg.max_sample_weight, 2.0)

    def test_to_dict_roundtrip(self):
        cfg1 = SamplingConfig(mode=SamplingMode.QUALITY_POSE_BALANCED, seed=123)
        d = cfg1.to_dict()
        cfg2 = SamplingConfig.from_mapping(d)
        self.assertEqual(cfg1, cfg2)


if __name__ == "__main__":
    unittest.main()
