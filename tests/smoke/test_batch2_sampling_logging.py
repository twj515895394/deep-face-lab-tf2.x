import shutil
import tempfile
import unittest
from pathlib import Path

from core.enhancements import EnhancementConfig
from samplelib.sampling.runtime import build_sampling_runtime
from tests.fixtures.batch2.build_synthetic_fixture import build_ordinary_fixture


class TestBatch2SamplingLogging(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="dfl_sampling_logging_test_"))
        cls.ordinary_dir = cls.temp_dir / "ordinary"
        build_ordinary_fixture(cls.ordinary_dir)

    @classmethod
    def tearDownClass(cls):
        if cls.temp_dir.exists():
            shutil.rmtree(cls.temp_dir)

    def test_startup_log_fields(self):
        cfg = EnhancementConfig.from_mapping({
            "training": {"enabled": True, "metadata_sampling": True},
            "sampling": {"mode": "legacy_random"}
        })
        runtime = build_sampling_runtime("src", self.ordinary_dir, cfg)
        log = runtime.startup_log

        self.assertEqual(log["role"], "src")
        self.assertEqual(log["requested_mode"], "legacy_random")
        self.assertEqual(log["effective_mode"], "legacy_random")
        self.assertIn("metadata_status", log)
        self.assertIn("sample_count", log)
        self.assertIn("matched_count", log)
        self.assertIn("matched_ratio", log)


if __name__ == "__main__":
    unittest.main()
