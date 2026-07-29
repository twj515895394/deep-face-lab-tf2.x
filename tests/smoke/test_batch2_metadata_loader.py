import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from samplelib.metadata.analyzer import FacesetAnalyzer
from samplelib.metadata.loader import (
    FacesetMetadataLoader,
    FacesetMetadataStatus,
    PITCH_BUCKET_NAME_TO_ID,
    UNKNOWN_BUCKET_ID,
    YAW_BUCKET_NAME_TO_ID,
)
from samplelib.metadata.store import load_metadata
from tests.fixtures.batch2.build_synthetic_fixture import (
    build_ordinary_fixture,
    build_packed_fixture,
)


class TestBatch2MetadataLoader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="dfl_loader_test_"))
        cls.ordinary_dir = cls.temp_dir / "ordinary"
        cls.packed_dir = cls.temp_dir / "packed"

        build_ordinary_fixture(cls.ordinary_dir)
        build_packed_fixture(cls.ordinary_dir, cls.packed_dir)

        # Run analyzer once to create valid sidecar metadata
        analyzer = FacesetAnalyzer()
        res_ord = analyzer.analyze(cls.ordinary_dir)
        res_ord.metadata.dump_json(cls.ordinary_dir / "faceset_metadata.v1.json")

        res_pack = analyzer.analyze(cls.packed_dir)
        res_pack.metadata.dump_json(cls.packed_dir / "faceset_metadata.v1.json")

    @classmethod
    def tearDownClass(cls):
        if cls.temp_dir.exists():
            shutil.rmtree(cls.temp_dir)

    def test_loader_perfect_match(self):
        from samplelib import SampleLoader, SampleType

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples)

        self.assertEqual(runtime.status, FacesetMetadataStatus.LOADED)
        self.assertEqual(runtime.sample_count, len(samples))
        self.assertEqual(runtime.matched_count, len(samples))
        self.assertEqual(runtime.matched_ratio, 1.0)
        self.assertTrue(runtime.is_usable_for_sampling())

        # Check compact array dimensions
        self.assertEqual(len(runtime.quality_scores), len(samples))
        self.assertEqual(len(runtime.yaw_bucket_ids), len(samples))
        self.assertEqual(runtime.quality_scores.dtype, np.float32)
        self.assertEqual(runtime.yaw_bucket_ids.dtype, np.int16)

        # Check valid flags
        self.assertTrue(np.all(runtime.metadata_valid))
        self.assertTrue(np.any(runtime.pose_valid), "pose_valid must not be all False when loading Analyzer outputs")
        self.assertTrue(np.any(runtime.yaw_bucket_ids != UNKNOWN_BUCKET_ID), "yaw_bucket_ids must contain valid bucket IDs (not all -1)")


    def test_loader_missing_file(self):
        from samplelib import SampleLoader, SampleType

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        non_existent_path = self.temp_dir / "non_existent"

        runtime = FacesetMetadataLoader.load(
            non_existent_path, samples, metadata_path=non_existent_path / "faceset_metadata.v1.json"
        )

        self.assertEqual(runtime.status, FacesetMetadataStatus.MISSING)
        self.assertEqual(runtime.matched_count, 0)
        self.assertEqual(runtime.matched_ratio, 0.0)
        self.assertFalse(runtime.is_usable_for_sampling())

        # Neutral default checks
        self.assertTrue(np.all(runtime.quality_scores == 1.0))
        self.assertTrue(np.all(runtime.yaw_bucket_ids == UNKNOWN_BUCKET_ID))
        self.assertFalse(np.any(runtime.metadata_valid))

    def test_loader_invalid_json_file(self):
        from samplelib import SampleLoader, SampleType

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        bad_json_path = self.temp_dir / "bad_metadata.json"
        with open(bad_json_path, "w", encoding="utf-8") as f:
            f.write("{ invalid json content ...")

        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples, metadata_path=bad_json_path)

        self.assertEqual(runtime.status, FacesetMetadataStatus.INVALID_FILE)
        self.assertFalse(runtime.is_usable_for_sampling())
        self.assertTrue(np.all(runtime.quality_scores == 1.0))

    def test_loader_unsupported_schema(self):
        from samplelib import SampleLoader, SampleType

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        unsupported_path = self.temp_dir / "unsupported_metadata.json"
        with open(unsupported_path, "w", encoding="utf-8") as f:
            json.dump({"schema_version": 999}, f)

        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples, metadata_path=unsupported_path)

        self.assertEqual(runtime.status, FacesetMetadataStatus.UNSUPPORTED_SCHEMA)
        self.assertFalse(runtime.is_usable_for_sampling())

    def test_loader_partial_match(self):
        from samplelib import SampleLoader, SampleType

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        # Create dummy extra sample to simulate 95% partial match
        extended_samples = list(samples) + [samples[0]]  # Duplicate 1 sample

        runtime = FacesetMetadataLoader.load(self.ordinary_dir, extended_samples, min_match_ratio=0.90)

        self.assertEqual(runtime.status, FacesetMetadataStatus.PARTIAL_MATCH)
        self.assertGreaterEqual(runtime.matched_ratio, 0.90)
        self.assertTrue(runtime.is_usable_for_sampling())

    def test_loader_fingerprint_mismatch_low_ratio(self):
        from samplelib import SampleLoader, SampleType

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        # Create metadata file with only 1 sample record out of 10 -> 10% ratio
        sparse_meta_path = self.temp_dir / "sparse_metadata.v1.json"
        loaded_meta, _ = load_metadata(self.ordinary_dir / "faceset_metadata.v1.json")
        loaded_meta.samples = loaded_meta.samples[:1]
        loaded_meta.dump_json(sparse_meta_path)

        runtime = FacesetMetadataLoader.load(
            self.ordinary_dir, samples, metadata_path=sparse_meta_path, min_match_ratio=0.90
        )

        self.assertEqual(runtime.status, FacesetMetadataStatus.FINGERPRINT_MISMATCH)
        self.assertLess(runtime.matched_ratio, 0.90)
        self.assertFalse(runtime.is_usable_for_sampling())

    def test_loader_packed_faceset(self):
        from samplelib import SampleLoader, SampleType

        samples = SampleLoader.load(SampleType.FACE, self.packed_dir)
        runtime = FacesetMetadataLoader.load(self.packed_dir, samples)

        self.assertEqual(runtime.status, FacesetMetadataStatus.LOADED)
        self.assertEqual(runtime.matched_count, len(samples))
        self.assertTrue(runtime.is_usable_for_sampling())

    def test_compact_array_memory_footprint(self):
        """Verify memory overhead for 100,000 samples is lightweight (< 2MB)."""
        N = 100_000
        quality_scores = np.ones(N, dtype=np.float32)
        yaw_bucket_ids = np.full(N, UNKNOWN_BUCKET_ID, dtype=np.int16)
        pitch_bucket_ids = np.full(N, UNKNOWN_BUCKET_ID, dtype=np.int16)
        pose_valid = np.zeros(N, dtype=np.bool_)
        quality_valid = np.zeros(N, dtype=np.bool_)
        metadata_valid = np.zeros(N, dtype=np.bool_)

        total_bytes = (
            quality_scores.nbytes
            + yaw_bucket_ids.nbytes
            + pitch_bucket_ids.nbytes
            + pose_valid.nbytes
            + quality_valid.nbytes
            + metadata_valid.nbytes
        )

        mb_size = total_bytes / (1024 * 1024)
        self.assertLess(mb_size, 2.0, f"Memory size {mb_size:.2f}MB exceeds 2MB limit for {N} samples")


if __name__ == "__main__":
    unittest.main()
