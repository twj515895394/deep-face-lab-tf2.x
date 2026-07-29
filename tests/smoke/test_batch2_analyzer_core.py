import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from samplelib.metadata.analyzer import FacesetAnalyzer, FacesetAnalyzerConfig
from tests.fixtures.batch2.build_synthetic_fixture import (
    build_ordinary_fixture,
    build_packed_fixture,
)


class TestBatch2AnalyzerCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="dfl_analyzer_test_"))
        cls.ordinary_dir = cls.temp_dir / "ordinary"
        cls.packed_dir = cls.temp_dir / "packed"

        build_ordinary_fixture(cls.ordinary_dir)
        cls.packed_file = build_packed_fixture(cls.ordinary_dir, cls.packed_dir)

    @classmethod
    def tearDownClass(cls):
        if cls.temp_dir.exists():
            shutil.rmtree(cls.temp_dir)

    def test_analyzer_ordinary_faceset(self):
        """Test full analyzer pipeline on Ordinary synthetic faceset."""
        analyzer = FacesetAnalyzer()
        res = analyzer.analyze(self.ordinary_dir)

        self.assertIsNotNone(res.metadata)
        self.assertEqual(res.metadata.schema_version, 1)
        self.assertEqual(res.metadata.dataset["format"], "ordinary")
        self.assertGreater(len(res.metadata.samples), 0)

        self.assertEqual(len(res.metadata.samples), 10)
        self.assertIn("total_samples", res.summary)
        self.assertIn("yaw_bucket_counts", res.summary)
        self.assertIn("quality_stats", res.summary)


    def test_analyzer_packed_faceset(self):
        """Test full analyzer pipeline on Packed synthetic faceset."""
        analyzer = FacesetAnalyzer()
        res = analyzer.analyze(self.packed_dir)

        self.assertIsNotNone(res.metadata)
        self.assertEqual(res.metadata.dataset["format"], "packed")
        self.assertEqual(len(res.metadata.samples), 10)
        self.assertEqual(len(res.failures), 0)

        # Check timing records
        self.assertIn("total_seconds", res.timing)
        self.assertIn("per_sample_ms", res.timing)


if __name__ == "__main__":
    unittest.main()
