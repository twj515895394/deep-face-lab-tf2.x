import json
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
from samplelib.metadata.contracts import PITCH_BUCKET_NAMES, YAW_BUCKET_NAMES
from samplelib.metadata.schema import FacesetMetadataV1
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
        cls.unicode_dir = cls.temp_dir / "中文分析集" / "ordinary"

        build_ordinary_fixture(cls.ordinary_dir)
        cls.packed_file = build_packed_fixture(cls.ordinary_dir, cls.packed_dir)
        build_ordinary_fixture(cls.unicode_dir)

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

    def test_analyzer_valid_buckets_are_canonical(self):
        """Every pose.valid=True sample must write only canonical yaw/pitch buckets."""
        res = FacesetAnalyzer().analyze(self.ordinary_dir)
        for sample in res.metadata.samples:
            pose = sample.get("pose") or {}
            if pose.get("valid"):
                self.assertIn(
                    pose.get("yaw_bucket"),
                    YAW_BUCKET_NAMES,
                    f"valid pose yaw must be canonical, got {pose.get('yaw_bucket')!r}",
                )
                self.assertIn(
                    pose.get("pitch_bucket"),
                    PITCH_BUCKET_NAMES,
                    f"valid pose pitch must be canonical, got {pose.get('pitch_bucket')!r}",
                )

    def test_analyzer_summary_keys_exact_set(self):
        """summary top-level keys and bucket count keys must match the fixed contract."""
        res = FacesetAnalyzer().analyze(self.ordinary_dir)
        from samplelib.metadata.summary_builder import CANONICAL_SUMMARY_KEYS

        expected_summary_keys = set(CANONICAL_SUMMARY_KEYS)
        self.assertEqual(set(res.summary.keys()), expected_summary_keys)

        expected_yaw = set(YAW_BUCKET_NAMES) | {"unknown"}
        expected_pitch = set(PITCH_BUCKET_NAMES) | {"unknown"}
        self.assertEqual(set(res.summary["yaw_bucket_counts"].keys()), expected_yaw)
        self.assertEqual(set(res.summary["pitch_bucket_counts"].keys()), expected_pitch)

        pose_cfg = res.metadata.analysis_config["pose"]
        self.assertEqual(pose_cfg["bucket_contract_version"], 1)
        self.assertEqual(pose_cfg["canonical_yaw_buckets"], list(YAW_BUCKET_NAMES))
        self.assertEqual(pose_cfg["canonical_pitch_buckets"], list(PITCH_BUCKET_NAMES))

    def test_analyzer_json_roundtrip_preserves_buckets(self):
        """JSON dump/load must preserve yaw/pitch bucket names exactly."""
        res = FacesetAnalyzer().analyze(self.ordinary_dir)
        path = self.temp_dir / "roundtrip_meta.v1.json"
        res.metadata.dump_json(path)
        loaded, val = FacesetMetadataV1.load_json(path)
        self.assertTrue(val.is_supported)
        self.assertEqual(len(loaded.samples), len(res.metadata.samples))
        before = {
            s["sample_id"]: (s["pose"]["yaw_bucket"], s["pose"]["pitch_bucket"])
            for s in res.metadata.samples
        }
        after = {
            s["sample_id"]: (s["pose"]["yaw_bucket"], s["pose"]["pitch_bucket"])
            for s in loaded.samples
        }
        self.assertEqual(before, after)

    def test_analyzer_unicode_filename_record_precise(self):
        """Unicode filename sample must be findable and keep bucket after analysis."""
        res = FacesetAnalyzer().analyze(self.unicode_dir)
        unicode_samples = [
            s for s in res.metadata.samples
            if "中文" in str(s.get("sample_key", "")) or "中文" in str(s.get("filename", ""))
        ]
        # Fixture uses 00005_中文文件名_dark.jpg
        if not unicode_samples:
            unicode_samples = [
                s for s in res.metadata.samples
                if any("中文" in str(v) for v in (s.get("sample_key"), s.get("filename"), s.get("sample_id")))
            ]
        # Fall back: search sample_key path components
        if not unicode_samples:
            for s in res.metadata.samples:
                key = str(s.get("sample_key", ""))
                if "中文文件名" in key or "中文" in key:
                    unicode_samples.append(s)
        self.assertGreaterEqual(len(unicode_samples), 1, "Unicode fixture filename record missing")
        rec = unicode_samples[0]
        self.assertIn("pose", rec)
        self.assertIn(rec["pose"]["yaw_bucket"], set(YAW_BUCKET_NAMES) | {"unknown"})
        self.assertIn(rec["pose"]["pitch_bucket"], set(PITCH_BUCKET_NAMES) | {"unknown"})


if __name__ == "__main__":
    unittest.main()
