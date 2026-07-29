import shutil
import tempfile
import unittest
from pathlib import Path

from core.enhancements import EnhancementConfig
from samplelib.sampling.runtime import build_sampling_runtime
from tests.fixtures.batch2.build_synthetic_fixture import build_ordinary_fixture


class TestBatch2SamplingFallback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="dfl_sampling_fallback_test_"))
        cls.ordinary_dir = cls.temp_dir / "ordinary"
        build_ordinary_fixture(cls.ordinary_dir)

    @classmethod
    def tearDownClass(cls):
        if cls.temp_dir.exists():
            shutil.rmtree(cls.temp_dir)

    def test_missing_metadata_triggers_fallback(self):
        # ordinary_dir does not have faceset_metadata.v1.json
        cfg = EnhancementConfig.from_mapping({
            "training": {"enabled": True, "metadata_sampling": True},
            "sampling": {"mode": "pose_balanced", "fallback_mode": "legacy_random"},
            "runtime": {"fallback_on_optional_error": True}
        })
        runtime = build_sampling_runtime("src", self.ordinary_dir, cfg)
        self.assertEqual(runtime.resolution.requested_mode, "pose_balanced")
        self.assertEqual(runtime.resolution.effective_mode, "legacy_random")
        self.assertIsNotNone(runtime.resolution.fallback_reason)

    def test_fallback_disabled_raises_error(self):
        cfg = EnhancementConfig.from_mapping({
            "training": {"enabled": True, "metadata_sampling": True},
            "sampling": {"mode": "pose_balanced", "fallback_mode": "legacy_random"},
            "runtime": {"fallback_on_optional_error": False}
        })
        with self.assertRaises(Exception):
            build_sampling_runtime("src", self.ordinary_dir, cfg)


if __name__ == "__main__":
    unittest.main()
