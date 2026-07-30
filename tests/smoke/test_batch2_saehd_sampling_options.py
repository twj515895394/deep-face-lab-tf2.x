import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from core.enhancements import (
    EnhancementConfig,
    detect_misplaced_batch2_top_level_keys,
    format_misplaced_batch2_keys_warning,
)
from samplelib.sampling.config import SamplingMode, resolve_metadata_path
from samplelib.sampling.policies import LegacyRandomPolicy, LegacyUniformYawPolicy
from samplelib.sampling.runtime import build_sampling_runtime
from tests.fixtures.batch2.build_synthetic_fixture import build_ordinary_fixture


class TestBatch2SAEHDSamplingOptions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="dfl_saehd_options_test_"))
        cls.ordinary_dir = cls.temp_dir / "ordinary"
        build_ordinary_fixture(cls.ordinary_dir)

    @classmethod
    def tearDownClass(cls):
        if cls.temp_dir.exists():
            shutil.rmtree(cls.temp_dir)

    def test_master_flag_off_uses_legacy(self):
        cfg = EnhancementConfig.from_mapping({
            "training": {"enabled": False, "metadata_sampling": False}
        })
        runtime = build_sampling_runtime("src", self.ordinary_dir, cfg, legacy_uniform_yaw=False)
        self.assertEqual(runtime.resolution.effective_mode, "legacy_random")
        self.assertIsInstance(runtime.policy, LegacyRandomPolicy)

        runtime_yaw = build_sampling_runtime("src", self.ordinary_dir, cfg, legacy_uniform_yaw=True)
        self.assertEqual(runtime_yaw.resolution.effective_mode, "legacy_uniform_yaw")
        self.assertIsInstance(runtime_yaw.policy, LegacyUniformYawPolicy)

    def test_src_dst_seed_derivation(self):
        cfg = EnhancementConfig.from_mapping({
            "training": {"enabled": True, "metadata_sampling": True},
            "sampling": {"mode": "legacy_random", "seed": None}
        })
        src_rt = build_sampling_runtime("src", self.ordinary_dir, cfg, base_seed=42)
        dst_rt = build_sampling_runtime("dst", self.ordinary_dir, cfg, base_seed=42)

        self.assertEqual(src_rt.policy.seed, 1042)
        self.assertEqual(dst_rt.policy.seed, 2042)
        self.assertNotEqual(src_rt.policy.seed, dst_rt.policy.seed)

    def test_side_specific_seeds_independent(self):
        cfg = EnhancementConfig.from_mapping({
            "training": {"enabled": True, "metadata_sampling": True},
            "sampling": {
                "src": {"mode": "legacy_random", "seed": 11},
                "dst": {"mode": "legacy_random", "seed": 22},
            },
        })
        src_rt = build_sampling_runtime("src", self.ordinary_dir, cfg, base_seed=42)
        dst_rt = build_sampling_runtime("dst", self.ordinary_dir, cfg, base_seed=42)
        self.assertEqual(src_rt.policy.seed, 11)
        self.assertEqual(dst_rt.policy.seed, 22)

    def test_src_dst_requested_modes_independent(self):
        cfg = EnhancementConfig.from_mapping({
            "training": {"enabled": True, "metadata_sampling": True},
            "sampling": {
                "src": {"mode": "quality_pose_balanced", "fallback_mode": "legacy_random"},
                "dst": {"mode": "pose_balanced", "fallback_mode": "legacy_random"},
            },
            "runtime": {"fallback_on_optional_error": True},
        })
        src_rt = build_sampling_runtime("src", self.ordinary_dir, cfg)
        dst_rt = build_sampling_runtime("dst", self.ordinary_dir, cfg)
        self.assertEqual(src_rt.resolution.requested_mode, "quality_pose_balanced")
        self.assertEqual(dst_rt.resolution.requested_mode, "pose_balanced")
        # No metadata fixture → both fallback, but requested modes stay side-specific
        self.assertEqual(src_rt.resolution.effective_mode, "legacy_random")
        self.assertEqual(dst_rt.resolution.effective_mode, "legacy_random")

    def test_gate_off_does_not_call_sample_loader(self):
        cfg = EnhancementConfig.from_mapping({
            "training": {"enabled": False, "metadata_sampling": True},
            "sampling": {"mode": "pose_balanced"},
        })
        with mock.patch("samplelib.sampling.runtime.SampleLoader.load") as load_mock:
            runtime = build_sampling_runtime("src", self.ordinary_dir, cfg)
            load_mock.assert_not_called()
        self.assertIsNone(runtime.metadata_runtime)
        self.assertEqual(runtime.startup_log["gates"]["open"], False)
        self.assertEqual(runtime.startup_log["metadata_status"], "disabled")

    def test_gate_matrix_runtime_no_load_when_closed(self):
        for enabled, meta in (
            (False, False),
            (False, True),
            (True, False),
        ):
            cfg = EnhancementConfig.from_mapping({
                "training": {"enabled": enabled, "metadata_sampling": meta},
                "sampling": {"mode": "legacy_random"},
            })
            with mock.patch(
                "samplelib.sampling.runtime.SampleLoader.load",
                side_effect=RuntimeError("should not load"),
            ) as load_mock:
                build_sampling_runtime("src", self.ordinary_dir, cfg)
                load_mock.assert_not_called()

    def test_gate_open_loads_samples(self):
        cfg = EnhancementConfig.from_mapping({
            "training": {"enabled": True, "metadata_sampling": True},
            "sampling": {"mode": "legacy_random"},
        })
        with mock.patch(
            "samplelib.sampling.runtime.SampleLoader.load",
            wraps=__import__("samplelib.SampleLoader", fromlist=["SampleLoader"]).SampleLoader.load,
        ) as load_mock:
            build_sampling_runtime("src", self.ordinary_dir, cfg)
            self.assertTrue(load_mock.called)

    def test_path_escape_raises_config_error(self):
        cfg = EnhancementConfig.from_mapping({
            "training": {"enabled": True, "metadata_sampling": True},
            "sampling": {
                "mode": "legacy_random",
                "metadata_path": "../escape.json",
            },
            "runtime": {"fallback_on_optional_error": True},
        })
        with self.assertRaises(ValueError):
            build_sampling_runtime("src", self.ordinary_dir, cfg)

    def test_flat_legacy_compatibility(self):
        cfg = EnhancementConfig.from_mapping({
            "training": {"enabled": True, "metadata_sampling": True},
            "sampling": {"mode": "legacy_random"},
        })
        src = build_sampling_runtime("src", self.ordinary_dir, cfg)
        dst = build_sampling_runtime("dst", self.ordinary_dir, cfg)
        self.assertEqual(src.resolution.requested_mode, "legacy_random")
        self.assertEqual(dst.resolution.requested_mode, "legacy_random")
        self.assertEqual(src.startup_log["config_source"], "base")

    def test_startup_log_contains_side_proof(self):
        cfg = EnhancementConfig.from_mapping({
            "training": {"enabled": True, "metadata_sampling": True},
            "sampling": {
                "fallback_mode": "legacy_random",
                "src": {"mode": "quality_pose_balanced"},
            },
            "runtime": {"fallback_on_optional_error": True},
        })
        src = build_sampling_runtime("src", self.ordinary_dir, cfg)
        self.assertEqual(src.startup_log["config_source"], "base+src_override")
        self.assertIn("metadata_path", src.startup_log)
        self.assertIn("gates", src.startup_log)
        self.assertEqual(src.startup_log["requested_mode"], "quality_pose_balanced")

    def test_saehd_explicit_sampling_config_preserves_config_source(self):
        """R1-02: SAEHD-style explicit SamplingConfig must keep real config_source."""
        cfg = EnhancementConfig.from_mapping({
            "training": {"enabled": True, "metadata_sampling": True},
            "sampling": {
                "fallback_mode": "legacy_random",
                "src": {"mode": "quality_pose_balanced"},
                "dst": {"mode": "pose_balanced"},
            },
            "runtime": {"fallback_on_optional_error": True},
        })
        src_cfg = cfg.sampling_config_for("src")
        src_source = cfg.sampling_config_source("src")
        dst_cfg = cfg.sampling_config_for("dst")
        dst_source = cfg.sampling_config_source("dst")

        src_rt = build_sampling_runtime(
            "src",
            self.ordinary_dir,
            cfg,
            sampling_config=src_cfg,
            sampling_config_source=src_source,
        )
        dst_rt = build_sampling_runtime(
            "dst",
            self.ordinary_dir,
            cfg,
            sampling_config=dst_cfg,
            sampling_config_source=dst_source,
        )
        self.assertEqual(src_rt.startup_log["config_source"], "base+src_override")
        self.assertEqual(dst_rt.startup_log["config_source"], "base+dst_override")
        self.assertEqual(src_rt.resolution.requested_mode, "quality_pose_balanced")
        self.assertEqual(dst_rt.resolution.requested_mode, "pose_balanced")
        # Without source arg, explicit path would wrongly become "explicit"
        bare = build_sampling_runtime(
            "src", self.ordinary_dir, cfg, sampling_config=src_cfg
        )
        self.assertEqual(bare.startup_log["config_source"], "explicit")

    def test_misplaced_top_level_keys_detected(self):
        opts = {"training": {"enabled": True}, "sampling": {}, "batch_size": 8}
        keys = detect_misplaced_batch2_top_level_keys(opts)
        self.assertEqual(keys, ["training", "sampling"])
        msg = format_misplaced_batch2_keys_warning(keys)
        self.assertIn("Unsupported top-level Batch 2 config keys detected", msg)
        self.assertIn("enhancements", msg)

    def test_options_json_nested_enhancements_kept_as_mapping(self):
        """ModelBase must keep enhancements nested object types (not stringify)."""
        payload = {
            "batch_size": 4,
            "enhancements": {
                "schema_version": 1,
                "training": {"enabled": True, "metadata_sampling": True},
                "sampling": {
                    "src": {"mode": "quality_pose_balanced"},
                    "dst": {"mode": "pose_balanced"},
                },
            },
        }
        # Simulate ModelBase nested injection branch
        val = payload["enhancements"]
        self.assertIsInstance(val, dict)
        cfg = EnhancementConfig.from_mapping(val)
        self.assertEqual(cfg.sampling_config_for("src").mode, SamplingMode.QUALITY_POSE_BALANCED)
        self.assertEqual(cfg.sampling_config_for("dst").mode, SamplingMode.POSE_BALANCED)
        # JSON roundtrip of the nested object stays valid
        restored = json.loads(json.dumps(cfg.to_dict(), ensure_ascii=False))
        again = EnhancementConfig.from_mapping(restored)
        self.assertEqual(again.sampling_config_for("src").mode, SamplingMode.QUALITY_POSE_BALANCED)

    def test_default_metadata_path_per_side(self):
        cfg = EnhancementConfig.from_mapping({
            "training": {"enabled": True, "metadata_sampling": True},
            "sampling": {"mode": "legacy_random"},
        })
        src = build_sampling_runtime("src", self.ordinary_dir, cfg)
        expected = resolve_metadata_path(self.ordinary_dir, None)
        self.assertEqual(Path(src.startup_log["metadata_path"]), expected)


if __name__ == "__main__":
    unittest.main()
