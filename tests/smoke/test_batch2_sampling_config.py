import math
import tempfile
import unittest
from pathlib import Path

from core.enhancements import EnhancementConfig
from samplelib.sampling.config import (
    SamplingConfig,
    SamplingMode,
    resolve_metadata_path,
)


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

    def test_unknown_field_warning(self):
        warnings = []
        SamplingConfig.from_mapping({"mode": "legacy", "not_a_field": 1}, warnings_out=warnings)
        self.assertTrue(any("not_a_field" in w for w in warnings))

    def test_resolve_metadata_path_default_and_relative(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "faceset"
            root.mkdir()
            default_path = resolve_metadata_path(root, None)
            self.assertEqual(default_path, root.resolve() / "faceset_metadata.v1.json")

            rel = resolve_metadata_path(root, "meta/faceset_metadata.v1.json")
            self.assertEqual(rel, (root / "meta" / "faceset_metadata.v1.json").resolve())

    def test_resolve_metadata_path_unicode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "中文 样本 集"
            root.mkdir()
            sub = "元数据"
            resolved = resolve_metadata_path(root, f"{sub}/faceset_metadata.v1.json")
            self.assertTrue(str(resolved).endswith(f"{sub}\\faceset_metadata.v1.json") or
                            str(resolved).endswith(f"{sub}/faceset_metadata.v1.json"))
            self.assertTrue(str(root.resolve()) in str(resolved))

    def test_resolve_metadata_path_rejects_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "faceset"
            root.mkdir()
            with self.assertRaises(ValueError):
                resolve_metadata_path(root, "../outside.json")

    def test_resolve_metadata_path_absolute_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "faceset"
            root.mkdir()
            abs_meta = Path(tmp) / "elsewhere" / "faceset_metadata.v1.json"
            abs_meta.parent.mkdir()
            resolved = resolve_metadata_path(root, str(abs_meta))
            self.assertEqual(resolved, abs_meta.resolve())


class TestBatch2EnhancementSamplingSides(unittest.TestCase):
    def test_no_enhancements_defaults(self):
        cfg = EnhancementConfig.from_mapping(None)
        self.assertFalse(cfg.is_enabled("training.metadata_sampling"))
        self.assertEqual(cfg.sampling_config.mode, SamplingMode.LEGACY)
        self.assertEqual(cfg.sampling_config_for("src").mode, SamplingMode.LEGACY)
        self.assertEqual(cfg.sampling_config_for("dst").mode, SamplingMode.LEGACY)

    def test_empty_enhancements(self):
        cfg = EnhancementConfig.from_mapping({})
        self.assertFalse(cfg.training_enabled)
        gate = cfg.metadata_sampling_gate_state()
        self.assertFalse(gate["open"])

    def test_dual_gate_matrix(self):
        cases = [
            (False, False, False),
            (False, True, False),
            (True, False, False),
            (True, True, True),
        ]
        for enabled, meta, expect_open in cases:
            cfg = EnhancementConfig.from_mapping({
                "training": {"enabled": enabled, "metadata_sampling": meta},
            })
            self.assertEqual(
                cfg.is_enabled("training.metadata_sampling"),
                expect_open,
                msg=f"enabled={enabled} meta={meta}",
            )
            self.assertEqual(cfg.metadata_sampling_gate_state()["open"], expect_open)

    def test_flat_config_applies_to_both_sides(self):
        cfg = EnhancementConfig.from_mapping({
            "sampling": {"mode": "pose_balanced", "uniform_mix": 0.2},
        })
        self.assertEqual(cfg.sampling_config_for("src").mode, SamplingMode.POSE_BALANCED)
        self.assertEqual(cfg.sampling_config_for("dst").mode, SamplingMode.POSE_BALANCED)
        self.assertEqual(cfg.sampling_config_for("src").uniform_mix, 0.2)
        self.assertEqual(cfg.sampling_config_source("src"), "base")
        self.assertEqual(cfg.sampling_config_source("dst"), "base")

    def test_src_dst_independent(self):
        cfg = EnhancementConfig.from_mapping({
            "sampling": {
                "src": {"mode": "quality_pose_balanced"},
                "dst": {"mode": "pose_balanced"},
            }
        })
        self.assertEqual(cfg.sampling_config_for("src").mode, SamplingMode.QUALITY_POSE_BALANCED)
        self.assertEqual(cfg.sampling_config_for("dst").mode, SamplingMode.POSE_BALANCED)
        # Base remains default legacy; not auto-copied from src.
        self.assertEqual(cfg.sampling_config.mode, SamplingMode.LEGACY)

    def test_base_plus_override(self):
        cfg = EnhancementConfig.from_mapping({
            "sampling": {
                "fallback_mode": "legacy_uniform_yaw",
                "uniform_mix": 0.15,
                "src": {"mode": "quality_pose_balanced", "quality_strength": 0.7},
                "dst": {"mode": "pose_balanced"},
            }
        })
        src = cfg.sampling_config_for("src")
        dst = cfg.sampling_config_for("dst")
        self.assertEqual(src.mode, SamplingMode.QUALITY_POSE_BALANCED)
        self.assertEqual(src.quality_strength, 0.7)
        self.assertEqual(src.fallback_mode, SamplingMode.LEGACY_UNIFORM_YAW)
        self.assertEqual(src.uniform_mix, 0.15)
        self.assertEqual(dst.mode, SamplingMode.POSE_BALANCED)
        self.assertEqual(dst.fallback_mode, SamplingMode.LEGACY_UNIFORM_YAW)
        self.assertEqual(cfg.sampling_config_source("src"), "base+src_override")
        self.assertEqual(cfg.sampling_config_source("dst"), "base+dst_override")

    def test_missing_side_uses_base_not_other_side(self):
        cfg = EnhancementConfig.from_mapping({
            "sampling": {
                "mode": "pose_balanced",
                "src": {"mode": "quality_pose_balanced"},
            }
        })
        self.assertEqual(cfg.sampling_config_for("src").mode, SamplingMode.QUALITY_POSE_BALANCED)
        self.assertEqual(cfg.sampling_config_for("dst").mode, SamplingMode.POSE_BALANCED)

    def test_invalid_side_type_warning(self):
        cfg = EnhancementConfig.from_mapping({
            "sampling": {
                "mode": "pose_balanced",
                "src": "pose_balanced",
            }
        })
        self.assertTrue(any("sampling.src" in w for w in cfg.config_warnings))
        # Invalid side ignored → both sides use base
        self.assertEqual(cfg.sampling_config_for("src").mode, SamplingMode.POSE_BALANCED)
        self.assertEqual(cfg.sampling_config_for("dst").mode, SamplingMode.POSE_BALANCED)

    def test_unknown_role_raises(self):
        cfg = EnhancementConfig.from_mapping({})
        with self.assertRaises(ValueError):
            cfg.sampling_config_for("other")

    def test_side_to_dict_roundtrip(self):
        raw = {
            "schema_version": 1,
            "training": {"enabled": True, "metadata_sampling": True},
            "sampling": {
                "uniform_mix": 0.1,
                "src": {"mode": "quality_pose_balanced"},
                "dst": {"mode": "pose_balanced"},
            },
        }
        cfg = EnhancementConfig.from_mapping(raw)
        again = EnhancementConfig.from_mapping(cfg.to_dict())
        self.assertEqual(
            cfg.sampling_config_for("src").mode,
            again.sampling_config_for("src").mode,
        )
        self.assertEqual(
            cfg.sampling_config_for("dst").mode,
            again.sampling_config_for("dst").mode,
        )
        self.assertEqual(cfg.to_dict()["sampling"]["src"]["mode"], "quality_pose_balanced")


if __name__ == "__main__":
    unittest.main()
