import unittest

from samplelib.metadata.incremental import (
    IncrementalPlan,
    build_incremental_plan,
    reconcile_and_finalize_samples,
)
from samplelib.metadata.schema import FacesetMetadataV1


class TestIncrementalMetadata(unittest.TestCase):
    def setUp(self):
        self.old_meta = FacesetMetadataV1(
            analyzer_version="v1.0",
            samples=[
                {
                    "sample_id": "00001",
                    "sample_key": "img_01.png",
                    "signature": "sig_01",
                    "valid": True,
                    "usable_for_sampling": True,
                    "pose_bucket_yaw": "front",
                    "pose_bucket_pitch": "center",
                    "quality_raw": {"valid": True, "sharpness_raw": 100.0, "exposure_score": 0.9},
                    "quality": {"sharpness_raw": 100.0, "quality_score": 0.8},
                },
                {
                    "sample_id": "00002",
                    "sample_key": "img_02.png",
                    "signature": "sig_02",
                    "valid": True,
                    "usable_for_sampling": True,
                    "pose_bucket_yaw": "left",
                    "pose_bucket_pitch": "center",
                    "quality_raw": {"valid": True, "sharpness_raw": 200.0, "exposure_score": 0.95},
                    "quality": {"sharpness_raw": 200.0, "quality_score": 0.9},
                },
                {
                    "sample_id": "00003",
                    "sample_key": "img_03.png",
                    "signature": "sig_03_old",
                    "valid": True,
                    "usable_for_sampling": True,
                    "pose_bucket_yaw": "right",
                    "pose_bucket_pitch": "center",
                    "quality_raw": {"valid": True, "sharpness_raw": 50.0, "exposure_score": 0.7},
                },
            ],
        )

    def test_plan_first_time(self):
        sigs = {"img_01.png": "sig_01"}
        plan = build_incremental_plan(None, sigs)
        self.assertFalse(plan.is_incremental)
        self.assertEqual(len(plan.added_sample_keys), 1)

    def test_plan_incremental_reuse_modify_add_delete(self):
        # img_01.png: same signature (reuse)
        # img_02.png: absent (removed)
        # img_03.png: signature changed to sig_03_new (recompute)
        # img_04.png: new image (added)
        current_sigs = {
            "img_01.png": "sig_01",
            "img_03.png": "sig_03_new",
            "img_04.png": "sig_04",
        }

        plan = build_incremental_plan(self.old_meta, current_sigs)

        self.assertTrue(plan.is_incremental)
        self.assertEqual(plan.reused_sample_keys, ["img_01.png"])
        self.assertEqual(plan.recompute_sample_keys, ["img_03.png"])
        self.assertEqual(plan.added_sample_keys, ["img_04.png"])
        self.assertEqual(plan.removed_sample_keys, ["img_02.png"])
        self.assertIn("img_01.png", plan.reused_sample_records)

    def test_plan_force(self):
        current_sigs = {"img_01.png": "sig_01"}
        plan = build_incremental_plan(self.old_meta, current_sigs, force=True)
        self.assertFalse(plan.is_incremental)
        self.assertEqual(plan.added_sample_keys, ["img_01.png"])

    def test_reconcile_and_finalize_samples(self):
        current_sigs = {
            "img_01.png": "sig_01",  # reused
            "img_04.png": "sig_04",  # new
        }
        plan = build_incremental_plan(self.old_meta, current_sigs)

        new_samples = [
            {
                "sample_id": "00004",
                "sample_key": "img_04.png",
                "signature": "sig_04",
                "valid": True,
                "usable_for_sampling": True,
                "pose_bucket_yaw": "front",
                "pose_bucket_pitch": "center",
                "quality_raw": {"valid": True, "sharpness_raw": 300.0, "exposure_score": 0.99},
            }
        ]

        final_samples, summary = reconcile_and_finalize_samples(plan, new_samples)

        self.assertEqual(len(final_samples), 2)
        self.assertEqual(summary["total_samples"], 2)
        self.assertEqual(summary["valid_samples"], 2)
        self.assertEqual(summary["pose_distribution_yaw"]["front"], 2)

        # Check quality scores are updated via Pass 2
        for s in final_samples:
            self.assertIn("quality", s)
            self.assertIn("quality_score", s["quality"])
            self.assertTrue(0.0 <= s["quality"]["quality_score"] <= 1.0)


if __name__ == "__main__":
    unittest.main()
