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
        """Legacy compact footprint for original arrays remains < 2MB."""
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

    def test_compact_array_memory_footprint_includes_all_contract_arrays(self):
        """All Ticket 14 contract arrays for 100k samples stay lightweight (< 2.5MB)."""
        N = 100_000
        arrays = [
            np.ones(N, dtype=np.float32),                 # quality_scores
            np.full(N, UNKNOWN_BUCKET_ID, dtype=np.int16),  # yaw
            np.full(N, UNKNOWN_BUCKET_ID, dtype=np.int16),  # pitch
            np.zeros(N, dtype=np.bool_),  # pose_valid
            np.zeros(N, dtype=np.bool_),  # quality_valid
            np.zeros(N, dtype=np.bool_),  # metadata_valid
            np.zeros(N, dtype=np.bool_),  # record_matched
            np.zeros(N, dtype=np.bool_),  # image_valid
            np.zeros(N, dtype=np.bool_),  # landmarks_valid
        ]
        total_bytes = sum(a.nbytes for a in arrays)
        mb_size = total_bytes / (1024 * 1024)
        # float32 + 2*int16 + 6*bool = 4+2+2+6 = 14 bytes/sample → ~1.34MB
        self.assertLess(mb_size, 2.5, f"Full contract arrays {mb_size:.2f}MB exceed 2.5MB for {N} samples")

    def test_loader_malformed_record_metadata_valid(self):
        from samplelib import SampleLoader, SampleType
        from samplelib.metadata.identity import build_sample_id, build_sample_key

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        bad_meta_path = self.temp_dir / "malformed_records.v1.json"

        s0_key = build_sample_key(getattr(samples[0], "filename"), is_packed=False, faceset_root=self.ordinary_dir)
        s0_id = build_sample_id(s0_key)

        bad_raw = {
            "schema_version": 1,
            "analyzer_version": "v1.0",
            "dataset": {"format": "ordinary", "sample_count": len(samples)},
            "samples": [
                "NOT_A_DICT_RECORD",
                {"sample_key": s0_key, "sample_id": s0_id},  # Empty record without pose/quality/image
                {"sample_key": s0_key, "sample_id": s0_id, "valid": True},  # Top-level valid only
            ],
        }

        with open(bad_meta_path, "w", encoding="utf-8") as f:
            json.dump(bad_raw, f)

        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples, metadata_path=bad_meta_path)
        self.assertFalse(runtime.metadata_valid[0])

    def test_loader_top_level_valid_only_is_not_metadata_valid(self):
        """Verify record with top-level 'valid: true' and NO child dicts gets metadata_valid=False."""
        from samplelib import SampleLoader, SampleType
        from samplelib.metadata.identity import build_sample_id, build_sample_key

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        s0_key = build_sample_key(getattr(samples[0], "filename"), is_packed=False, faceset_root=self.ordinary_dir)
        s0_id = build_sample_id(s0_key)

        raw = {
            "schema_version": 1,
            "dataset": {"format": "ordinary", "sample_count": 1},
            "samples": [{"sample_key": s0_key, "sample_id": s0_id, "valid": True}],
        }
        path = self.temp_dir / "top_level_only.v1.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw, f)

        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples, metadata_path=path)
        self.assertFalse(runtime.metadata_valid[0])

    def test_loader_does_not_treat_string_false_as_pose_valid(self):
        """Verify string 'false' for pose.valid is not parsed as True in Python."""
        from samplelib import SampleLoader, SampleType
        from samplelib.metadata.identity import build_sample_id, build_sample_key

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        s0_key = build_sample_key(getattr(samples[0], "filename"), is_packed=False, faceset_root=self.ordinary_dir)
        s0_id = build_sample_id(s0_key)

        raw = {
            "schema_version": 1,
            "dataset": {"format": "ordinary", "sample_count": 1},
            "samples": [
                {
                    "sample_key": s0_key,
                    "sample_id": s0_id,
                    "pose": {"valid": "false", "yaw_bucket": "center"},
                }
            ],
        }
        path = self.temp_dir / "string_false_pose.v1.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw, f)

        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples, metadata_path=path)
        self.assertFalse(runtime.pose_valid[0])

    def test_loader_extreme_maps_unknown_and_emits_warning(self):
        """Verify legacy 'extreme' yaw maps to unknown ID (-1) and emits warning."""
        from samplelib import SampleLoader, SampleType
        from samplelib.metadata.identity import build_sample_id, build_sample_key

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        s0_key = build_sample_key(getattr(samples[0], "filename"), is_packed=False, faceset_root=self.ordinary_dir)
        s0_id = build_sample_id(s0_key)

        raw = {
            "schema_version": 1,
            "dataset": {"format": "ordinary", "sample_count": 1},
            "samples": [
                {
                    "sample_key": s0_key,
                    "sample_id": s0_id,
                    "pose": {"valid": True, "yaw_bucket": "extreme", "pitch_bucket": "level"},
                }
            ],
        }
        path = self.temp_dir / "extreme_yaw.v1.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw, f)

        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples, metadata_path=path)
        self.assertEqual(runtime.yaw_bucket_ids[0], UNKNOWN_BUCKET_ID)
        self.assertFalse(runtime.pose_valid[0])
        unknown_warns = [w for w in runtime.warnings if "UNKNOWN_YAW_BUCKET" in w]
        self.assertGreater(len(unknown_warns), 0)

    def test_loader_alias_warnings_are_aggregated_and_bounded(self):
        from samplelib import SampleLoader, SampleType
        from samplelib.metadata.identity import build_sample_id, build_sample_key

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        alias_meta_path = self.temp_dir / "alias_warnings.v1.json"

        meta_samples = []
        for s in samples:
            key = build_sample_key(getattr(s, "filename"), is_packed=False, faceset_root=self.ordinary_dir)
            sid = build_sample_id(key)
            meta_samples.append({
                "sample_key": key,
                "sample_id": sid,
                "valid": True,
                "pose": {"valid": True, "yaw_bucket": "front", "pitch_bucket": "center"},
            })

        alias_raw = {
            "schema_version": 1,
            "analyzer_version": "v1.0",
            "dataset": {"format": "ordinary", "sample_count": len(samples)},
            "samples": meta_samples,
        }

        with open(alias_meta_path, "w", encoding="utf-8") as f:
            json.dump(alias_raw, f)

        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples, metadata_path=alias_meta_path)

        alias_warns = [w for w in runtime.warnings if "LEGACY_YAW_ALIAS_USED" in w]
        self.assertGreater(len(alias_warns), 0)
        warn_str = alias_warns[0]
        self.assertIn("count=", warn_str)

        # Assert examples in warning is strictly bounded to <= 5 examples
        if "examples=[" in warn_str:
            ex_content = warn_str.split("examples=[")[1].rstrip("]")
            ex_items = [x for x in ex_content.split(",") if x.strip()]
            self.assertLessEqual(len(ex_items), 5)

    def test_loader_unknown_pitch_retains_valid_yaw(self):
        from samplelib import SampleLoader, SampleType
        from samplelib.metadata.identity import build_sample_id, build_sample_key

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        pitch_meta_path = self.temp_dir / "unknown_pitch.v1.json"

        s0_key = build_sample_key(getattr(samples[0], "filename"), is_packed=False, faceset_root=self.ordinary_dir)
        s0_id = build_sample_id(s0_key)

        pitch_raw = {
            "schema_version": 1,
            "analyzer_version": "v1.0",
            "dataset": {"format": "ordinary", "sample_count": len(samples)},
            "samples": [
                {
                    "sample_key": s0_key,
                    "sample_id": s0_id,
                    "valid": True,
                    "pose": {"valid": True, "yaw_bucket": "center", "pitch_bucket": "unknown_pitch_str"},
                }
            ],
        }

        with open(pitch_meta_path, "w", encoding="utf-8") as f:
            json.dump(pitch_raw, f)

        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples, metadata_path=pitch_meta_path)
        self.assertTrue(runtime.pose_valid[0])
        self.assertEqual(runtime.pitch_bucket_ids[0], UNKNOWN_BUCKET_ID)
        self.assertNotEqual(runtime.yaw_bucket_ids[0], UNKNOWN_BUCKET_ID)

    def test_loader_schema_warnings_are_aggregated_by_code(self):
        """Schema issues must be collapsed to one SCHEMA_ISSUE line per code with count=."""
        from samplelib import SampleLoader, SampleType
        from samplelib.metadata.identity import build_sample_id, build_sample_key

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        meta_samples = []
        for s in samples:
            key = build_sample_key(getattr(s, "filename"), is_packed=False, faceset_root=self.ordinary_dir)
            sid = build_sample_id(key)
            meta_samples.append({
                "sample_key": key,
                "sample_id": sid,
                "pose": {"valid": True, "yaw_bucket": "front", "pitch_bucket": "center"},
            })

        path = self.temp_dir / "schema_agg.v1.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"schema_version": 1, "dataset": {}, "samples": meta_samples}, f)

        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples, metadata_path=path)
        schema_yaw = [w for w in runtime.warnings if "SCHEMA_ISSUE [LEGACY_YAW_BUCKET_ALIAS]" in w]
        schema_pitch = [w for w in runtime.warnings if "SCHEMA_ISSUE [LEGACY_PITCH_BUCKET_ALIAS]" in w]
        self.assertEqual(len(schema_yaw), 1)
        self.assertEqual(len(schema_pitch), 1)
        self.assertIn(f"count={len(samples)}", schema_yaw[0])
        self.assertIn(f"count={len(samples)}", schema_pitch[0])
        self.assertIn("examples=[", schema_yaw[0])

    def test_loader_total_warning_count_is_bounded(self):
        """Total RuntimeMetadata.warnings must not grow with per-sample issue volume."""
        from samplelib import SampleLoader, SampleType
        from samplelib.metadata.identity import build_sample_id, build_sample_key
        from samplelib.metadata.loader import _MAX_RUNTIME_WARNINGS

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        meta_samples = []
        for s in samples:
            key = build_sample_key(getattr(s, "filename"), is_packed=False, faceset_root=self.ordinary_dir)
            sid = build_sample_id(key)
            meta_samples.append({
                "sample_key": key,
                "sample_id": sid,
                "pose": {"valid": "BROKEN", "yaw_bucket": "front", "pitch_bucket": "nope"},
            })

        path = self.temp_dir / "warn_bound.v1.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"schema_version": 1, "dataset": {}, "samples": meta_samples}, f)

        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples, metadata_path=path)
        self.assertLessEqual(len(runtime.warnings), _MAX_RUNTIME_WARNINGS)
        # Must be O(codes), not O(samples)
        self.assertLess(len(runtime.warnings), len(samples))

    def test_loader_100k_alias_records_do_not_create_100k_runtime_warnings(self):
        """100k legacy alias records must not produce ~100k RuntimeMetadata.warnings."""
        from samplelib import SampleLoader, SampleType
        from samplelib.metadata.identity import build_sample_id, build_sample_key

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        n_alias = 100_000
        meta_samples = []
        # Keep real sample IDs first so match-time path still works, then pad with aliases.
        for s in samples:
            key = build_sample_key(getattr(s, "filename"), is_packed=False, faceset_root=self.ordinary_dir)
            sid = build_sample_id(key)
            meta_samples.append({
                "sample_key": key,
                "sample_id": sid,
                "pose": {"valid": True, "yaw_bucket": "front", "pitch_bucket": "level"},
            })
        for i in range(n_alias - len(samples)):
            key = f"pad_{i:06d}.jpg"
            meta_samples.append({
                "sample_key": key,
                "sample_id": build_sample_id(key),
                "pose": {"valid": True, "yaw_bucket": "front", "pitch_bucket": "level"},
            })

        path = self.temp_dir / "alias_100k.v1.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"schema_version": 1, "dataset": {}, "samples": meta_samples}, f)

        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples, metadata_path=path)
        schema_alias = [w for w in runtime.warnings if "SCHEMA_ISSUE [LEGACY_YAW_BUCKET_ALIAS]" in w]
        self.assertEqual(len(schema_alias), 1)
        self.assertIn(f"count={n_alias}", schema_alias[0])
        self.assertLess(len(runtime.warnings), 50)
        self.assertNotEqual(len(runtime.warnings), n_alias)

    def test_loader_mixed_valid_and_malformed_child_is_not_metadata_valid(self):
        """pose='BROKEN' + quality={} must not be metadata_valid."""
        from samplelib import SampleLoader, SampleType
        from samplelib.metadata.identity import build_sample_id, build_sample_key

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        s0_key = build_sample_key(getattr(samples[0], "filename"), is_packed=False, faceset_root=self.ordinary_dir)
        s0_id = build_sample_id(s0_key)

        raw = {
            "schema_version": 1,
            "dataset": {"format": "ordinary", "sample_count": 1},
            "samples": [{
                "sample_key": s0_key,
                "sample_id": s0_id,
                "pose": "BROKEN",
                "quality": {},
            }],
        }
        path = self.temp_dir / "mixed_malformed.v1.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw, f)

        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples, metadata_path=path)
        self.assertFalse(runtime.metadata_valid[0])

    def test_loader_valid_yaw_pitch_ids_in_range(self):
        """All valid yaw IDs in 0..6 and pitch IDs in 0..2."""
        from samplelib import SampleLoader, SampleType

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples)

        valid_yaw = runtime.yaw_bucket_ids[runtime.pose_valid]
        self.assertTrue(len(valid_yaw) > 0)
        self.assertTrue(np.all((valid_yaw >= 0) & (valid_yaw <= 6)))

        valid_pitch_mask = runtime.pitch_bucket_ids != UNKNOWN_BUCKET_ID
        valid_pitch = runtime.pitch_bucket_ids[valid_pitch_mask]
        if len(valid_pitch) > 0:
            self.assertTrue(np.all((valid_pitch >= 0) & (valid_pitch <= 2)))

    def test_loader_loaded_status_does_not_imply_all_pose_valid(self):
        """LOADED status must not be confused with every sample having pose_valid=True."""
        from samplelib import SampleLoader, SampleType
        from samplelib.metadata.store import load_metadata

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        loaded_meta, _ = load_metadata(self.ordinary_dir / "faceset_metadata.v1.json")
        self.assertGreaterEqual(len(loaded_meta.samples), 1)
        loaded_meta.samples[0]["pose"]["valid"] = False
        loaded_meta.samples[0]["pose"]["yaw_bucket"] = "center"

        path = self.temp_dir / "loaded_not_all_pose.v1.json"
        loaded_meta.dump_json(path)

        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples, metadata_path=path)
        self.assertEqual(runtime.status, FacesetMetadataStatus.LOADED)
        self.assertEqual(runtime.matched_count, len(samples))
        self.assertFalse(bool(np.all(runtime.pose_valid)))

    def test_loader_image_pose_quality_metadata_semantics_separated(self):
        """image/pose/quality/metadata validity arrays are independent."""
        from samplelib import SampleLoader, SampleType
        from samplelib.metadata.identity import build_sample_id, build_sample_key

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        s0_key = build_sample_key(getattr(samples[0], "filename"), is_packed=False, faceset_root=self.ordinary_dir)
        s0_id = build_sample_id(s0_key)

        raw = {
            "schema_version": 1,
            "dataset": {},
            "samples": [{
                "sample_key": s0_key,
                "sample_id": s0_id,
                "image": {"valid": True},
                "landmarks": {"valid": True},
                "pose": {"valid": False, "yaw_bucket": "center", "pitch_bucket": "level"},
                "quality": {"quality_score": 0.7},
            }],
        }
        path = self.temp_dir / "sem_sep.v1.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw, f)

        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples, metadata_path=path)
        self.assertTrue(runtime.record_matched[0])
        self.assertTrue(runtime.metadata_valid[0])
        self.assertTrue(runtime.image_valid[0])
        self.assertTrue(runtime.landmarks_valid[0])
        self.assertFalse(runtime.pose_valid[0])
        self.assertTrue(runtime.quality_valid[0])
        self.assertEqual(runtime.yaw_bucket_ids[0], YAW_BUCKET_NAME_TO_ID["center"])

    def test_loader_record_matched_distinguishes_unmatched_and_malformed(self):
        """record_matched is true for unique ID hits even when structure is malformed."""
        from samplelib import SampleLoader, SampleType
        from samplelib.metadata.identity import build_sample_id, build_sample_key

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        s0_key = build_sample_key(getattr(samples[0], "filename"), is_packed=False, faceset_root=self.ordinary_dir)
        s0_id = build_sample_id(s0_key)
        s1_key = build_sample_key(getattr(samples[1], "filename"), is_packed=False, faceset_root=self.ordinary_dir)
        s1_id = build_sample_id(s1_key)

        raw = {
            "schema_version": 1,
            "dataset": {},
            "samples": [
                # matched + malformed structure
                {"sample_key": s0_key, "sample_id": s0_id, "pose": "BROKEN", "quality": {}},
                # matched + structural OK
                {
                    "sample_key": s1_key,
                    "sample_id": s1_id,
                    "image": {"valid": True},
                    "pose": {"valid": True, "yaw_bucket": "center", "pitch_bucket": "level"},
                },
            ],
        }
        path = self.temp_dir / "matched_vs_malformed.v1.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw, f)

        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples, metadata_path=path)
        self.assertTrue(runtime.record_matched[0])
        self.assertFalse(runtime.metadata_valid[0])
        self.assertTrue(runtime.record_matched[1])
        self.assertTrue(runtime.metadata_valid[1])
        # Unmatched remaining samples
        if len(samples) > 2:
            self.assertFalse(bool(runtime.record_matched[2:].any()))

    def test_loader_image_valid_uses_nested_contract(self):
        from samplelib import SampleLoader, SampleType
        from samplelib.metadata.identity import build_sample_id, build_sample_key

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        s0_key = build_sample_key(getattr(samples[0], "filename"), is_packed=False, faceset_root=self.ordinary_dir)
        s0_id = build_sample_id(s0_key)

        raw = {
            "schema_version": 1,
            "dataset": {},
            "samples": [{
                "sample_key": s0_key,
                "sample_id": s0_id,
                "image": {"valid": "false"},
                "pose": {"valid": True, "yaw_bucket": "center"},
            }],
        }
        path = self.temp_dir / "image_valid_nested.v1.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw, f)

        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples, metadata_path=path)
        self.assertTrue(runtime.metadata_valid[0])
        self.assertFalse(runtime.image_valid[0])
        self.assertTrue(runtime.pose_valid[0])

    def test_loader_landmarks_valid_uses_nested_contract(self):
        from samplelib import SampleLoader, SampleType
        from samplelib.metadata.identity import build_sample_id, build_sample_key

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        s0_key = build_sample_key(getattr(samples[0], "filename"), is_packed=False, faceset_root=self.ordinary_dir)
        s0_id = build_sample_id(s0_key)

        raw = {
            "schema_version": 1,
            "dataset": {},
            "samples": [{
                "sample_key": s0_key,
                "sample_id": s0_id,
                "landmarks": {"valid": False},
                "pose": {"valid": True, "yaw_bucket": "center", "pitch_bucket": "level"},
            }],
        }
        path = self.temp_dir / "landmarks_valid_nested.v1.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw, f)

        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples, metadata_path=path)
        self.assertTrue(runtime.metadata_valid[0])
        self.assertFalse(runtime.landmarks_valid[0])
        self.assertTrue(runtime.pose_valid[0])

    def test_loader_validity_arrays_are_independent(self):
        """metadata/image/landmarks/pose/quality flags can each fail independently."""
        from samplelib import SampleLoader, SampleType
        from samplelib.metadata.identity import build_sample_id, build_sample_key

        samples = list(SampleLoader.load(SampleType.FACE, self.ordinary_dir))
        keys_ids = []
        for s in samples[:4]:
            k = build_sample_key(getattr(s, "filename"), is_packed=False, faceset_root=self.ordinary_dir)
            keys_ids.append((k, build_sample_id(k)))

        # 0: image false, others true
        # 1: landmarks false
        # 2: pose false
        # 3: quality invalid (missing score)
        recs = [
            {
                "sample_key": keys_ids[0][0], "sample_id": keys_ids[0][1],
                "image": {"valid": False}, "landmarks": {"valid": True},
                "pose": {"valid": True, "yaw_bucket": "center", "pitch_bucket": "level"},
                "quality": {"quality_score": 0.9},
            },
            {
                "sample_key": keys_ids[1][0], "sample_id": keys_ids[1][1],
                "image": {"valid": True}, "landmarks": {"valid": False},
                "pose": {"valid": True, "yaw_bucket": "center", "pitch_bucket": "level"},
                "quality": {"quality_score": 0.9},
            },
            {
                "sample_key": keys_ids[2][0], "sample_id": keys_ids[2][1],
                "image": {"valid": True}, "landmarks": {"valid": True},
                "pose": {"valid": False, "yaw_bucket": "center", "pitch_bucket": "level"},
                "quality": {"quality_score": 0.9},
            },
            {
                "sample_key": keys_ids[3][0], "sample_id": keys_ids[3][1],
                "image": {"valid": True}, "landmarks": {"valid": True},
                "pose": {"valid": True, "yaw_bucket": "center", "pitch_bucket": "level"},
                "quality": {},
            },
        ]
        path = self.temp_dir / "independent_flags.v1.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"schema_version": 1, "dataset": {}, "samples": recs}, f)

        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples, metadata_path=path)
        self.assertTrue(np.all(runtime.record_matched[:4]))
        self.assertTrue(np.all(runtime.metadata_valid[:4]))

        self.assertFalse(runtime.image_valid[0])
        self.assertTrue(runtime.landmarks_valid[0])
        self.assertTrue(runtime.pose_valid[0])
        self.assertTrue(runtime.quality_valid[0])

        self.assertTrue(runtime.image_valid[1])
        self.assertFalse(runtime.landmarks_valid[1])
        self.assertTrue(runtime.pose_valid[1])

        self.assertTrue(runtime.image_valid[2])
        self.assertTrue(runtime.landmarks_valid[2])
        self.assertFalse(runtime.pose_valid[2])
        self.assertTrue(runtime.quality_valid[2])

        self.assertTrue(runtime.image_valid[3])
        self.assertTrue(runtime.landmarks_valid[3])
        self.assertTrue(runtime.pose_valid[3])
        self.assertFalse(runtime.quality_valid[3])

    def test_loader_malformed_sibling_preserves_independent_child_flags(self):
        """Malformed sibling (pose string) must not zero independent image/landmarks/quality flags.

        Sampling safety still requires metadata_valid & business_valid, so usable masks stay false.
        Existing pose='BROKEN' + quality={} still yields metadata_valid=False.
        """
        from samplelib import SampleLoader, SampleType
        from samplelib.metadata.identity import build_sample_id, build_sample_key

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        s0_key = build_sample_key(
            getattr(samples[0], "filename"), is_packed=False, faceset_root=self.ordinary_dir
        )
        s0_id = build_sample_id(s0_key)

        raw = {
            "schema_version": 1,
            "dataset": {"format": "ordinary", "sample_count": 1},
            "samples": [{
                "sample_key": s0_key,
                "sample_id": s0_id,
                "image": {"valid": True},
                "landmarks": {"valid": True},
                "pose": "BROKEN",
                "quality": {"quality_score": 0.8},
            }],
        }
        path = self.temp_dir / "malformed_sibling_independent.v1.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw, f)

        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples, metadata_path=path)

        self.assertTrue(bool(runtime.record_matched[0]))
        self.assertFalse(bool(runtime.metadata_valid[0]))
        self.assertTrue(bool(runtime.image_valid[0]))
        self.assertTrue(bool(runtime.landmarks_valid[0]))
        self.assertTrue(bool(runtime.quality_valid[0]))
        self.assertFalse(bool(runtime.pose_valid[0]))
        self.assertAlmostEqual(float(runtime.quality_scores[0]), 0.8, places=5)

        usable_pose = runtime.usable_for_pose_sampling()
        usable_quality = runtime.usable_for_quality_sampling()
        self.assertFalse(bool(usable_pose[0]))
        self.assertFalse(bool(usable_quality[0]))


if __name__ == "__main__":
    unittest.main()


