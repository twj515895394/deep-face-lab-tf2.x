import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from samplelib.metadata.fingerprint import (
    SampleSignature,
    build_dataset_fingerprint,
    build_sample_signature,
)
from samplelib.metadata.identity import build_sample_id
from samplelib.metadata.schema import (
    FacesetMetadataV1,
    MetadataValidationIssue,
    sanitize_finite_json,
)


class TestBatch2MetadataSchema(unittest.TestCase):
    def test_sample_signature_and_dataset_fingerprint(self):
        """Verify signature building and deterministic dataset fingerprint regardless of input order."""
        sig1 = build_sample_signature("a_sample.jpg", byte_size=1024, mtime_ns=1600000000000000000)
        sig2 = build_sample_signature("b_sample.jpg", byte_size=2048, mtime_ns=1600000001000000000)
        sig3 = build_sample_signature("c_sample.jpg", byte_size=4096, packed_offset=512)

        # Order 1: a, b, c
        fp1 = build_dataset_fingerprint([sig1, sig2, sig3])
        # Order 2: c, a, b
        fp2 = build_dataset_fingerprint([sig3, sig1, sig2])

        self.assertEqual(fp1, fp2, "Dataset fingerprint must be independent of list insertion order")
        self.assertEqual(len(fp1), 64)

    def test_sanitize_finite_json(self):
        """Verify NaN and Inf floats are sanitized to None and logged."""
        issues = []
        raw_data = {
            "valid_float": 1.234,
            "nan_val": float("nan"),
            "inf_val": float("inf"),
            "nested": {"bad": float("nan")},
        }

        sanitized = sanitize_finite_json(raw_data, issues)
        self.assertEqual(sanitized["valid_float"], 1.234)
        self.assertIsNone(sanitized["nan_val"])
        self.assertIsNone(sanitized["inf_val"])
        self.assertIsNone(sanitized["nested"]["bad"])

        self.assertEqual(len(issues), 3)

        # Verify json.dumps succeeds without allow_nan
        encoded = json.dumps(sanitized, allow_nan=False)
        self.assertIn('"nan_val": null', encoded)

    def test_schema_v1_validation_and_roundtrip(self):
        """Verify Schema V1 construction, JSON dumping/loading, and roundtrip consistency."""
        key1 = "00001.jpg"
        key2 = "00002.jpg"
        id1 = build_sample_id(key1)
        id2 = build_sample_id(key2)

        sample1 = {
            "sample_id": id1,
            "sample_key": key1,
            "signature": build_sample_signature(key1, 1024).to_dict(),
            "quality": {"score": 0.85},
            "pose": {"pitch": 0.1, "yaw": -0.2, "roll": 0.0},
        }
        sample2 = {
            "sample_id": id2,
            "sample_key": key2,
            "signature": build_sample_signature(key2, 2048).to_dict(),
            "quality": {"score": float("nan")},  # Should be sanitized
            "pose": {"pitch": 0.0, "yaw": 0.0, "roll": 0.0},
        }

        metadata = FacesetMetadataV1(
            dataset={"format": "ordinary", "sample_count": 2},
            samples=[sample1, sample2],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "metadata.json"
            metadata.dump_json(json_path)

            loaded_metadata, validation = FacesetMetadataV1.load_json(json_path)
            self.assertTrue(validation.is_supported)
            self.assertEqual(loaded_metadata.schema_version, 1)
            self.assertEqual(len(loaded_metadata.samples), 2)
            self.assertIsNone(loaded_metadata.samples[1]["quality"]["score"])

    def test_schema_rejects_non_mapping_pose(self):
        """Verify Schema logs INVALID_POSE_MAPPING when pose is not a dict."""
        raw = {
            "schema_version": 1,
            "samples": [
                {
                    "sample_key": "00001.jpg",
                    "sample_id": build_sample_id("00001.jpg"),
                    "pose": "NON_MAPPING_STRING_POSE",
                }
            ],
        }
        _, val = FacesetMetadataV1.from_mapping(raw)
        self.assertFalse(val.is_valid)
        codes = [i.code for i in val.issues]
        self.assertIn("INVALID_POSE_MAPPING", codes)

    def test_schema_rejects_invalid_pose_valid_type(self):
        """Verify Schema logs INVALID_POSE_VALID_TYPE when pose.valid is not boolean-compatible."""
        raw = {
            "schema_version": 1,
            "samples": [
                {
                    "sample_key": "00001.jpg",
                    "sample_id": build_sample_id("00001.jpg"),
                    "pose": {"valid": "BROKEN_STRING", "yaw_bucket": "center"},
                }
            ],
        }
        _, val = FacesetMetadataV1.from_mapping(raw)
        self.assertFalse(val.is_valid)
        codes = [i.code for i in val.issues]
        self.assertIn("INVALID_POSE_VALID_TYPE", codes)

    def test_schema_reports_legacy_yaw_alias(self):
        """Verify Schema logs LEGACY_YAW_BUCKET_ALIAS when legacy alias like 'front' is used."""
        raw = {
            "schema_version": 1,
            "samples": [
                {
                    "sample_key": "00001.jpg",
                    "sample_id": build_sample_id("00001.jpg"),
                    "pose": {"valid": True, "yaw_bucket": "front", "pitch_bucket": "center"},
                }
            ],
        }
        _, val = FacesetMetadataV1.from_mapping(raw)
        self.assertFalse(val.is_valid)
        codes = [i.code for i in val.issues]
        self.assertIn("LEGACY_YAW_BUCKET_ALIAS", codes)
        self.assertIn("LEGACY_PITCH_BUCKET_ALIAS", codes)


if __name__ == "__main__":
    unittest.main()

