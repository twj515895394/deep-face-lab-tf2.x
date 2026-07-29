import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from core.enhancements import EnhancementConfig
from samplelib.sampling.policies import LegacyRandomPolicy, LegacyUniformYawPolicy, PoseBalancedPolicy
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


if __name__ == "__main__":
    unittest.main()
