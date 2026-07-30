import unittest

from samplelib.metadata.incremental import (
    IncrementalPlan,
    build_incremental_plan,
    reconcile_and_finalize_samples,
)
from samplelib.metadata.schema import FacesetMetadataV1
from samplelib.metadata.summary_builder import CANONICAL_SUMMARY_KEYS


def _nested_sample(
    sample_id: str,
    sample_key: str,
    signature,
    yaw: str = "center",
    pitch: str = "level",
    sharpness: float = 100.0,
    exposure: float = 0.9,
    issues=None,
):
    """Canonical nested record shape matching FacesetAnalyzer pass1 + quality."""
    return {
        "sample_id": sample_id,
        "sample_key": sample_key,
        "signature": signature,
        "image": {"valid": True, "height": 64, "width": 64, "channels": 3},
        "landmarks": {"valid": True},
        "pose": {
            "valid": True,
            "pitch": 0.0,
            "yaw": 0.0,
            "roll": 0.0,
            "yaw_bucket": yaw,
            "pitch_bucket": pitch,
        },
        "quality_raw": {
            "valid": True,
            "sharpness_raw": sharpness,
            "dark_ratio": 0.1,
            "bright_ratio": 0.1,
            "exposure_score": exposure,
        },
        "quality": {
            "sharpness_raw": sharpness,
            "quality_score": 0.8,
            "exposure_score": exposure,
        },
        "issues": list(issues or []),
    }


class TestIncrementalMetadata(unittest.TestCase):
    def setUp(self):
        self.old_meta = FacesetMetadataV1(
            analyzer_version="v1.0",
            samples=[
                _nested_sample("00001", "img_01.png", "sig_01", yaw="center", sharpness=100.0),
                _nested_sample("00002", "img_02.png", "sig_02", yaw="major_left", sharpness=200.0),
                _nested_sample(
                    "00003",
                    "img_03.png",
                    "sig_03_old",
                    yaw="major_right",
                    sharpness=50.0,
                    exposure=0.7,
                ),
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

    def test_reconcile_and_finalize_samples_canonical_summary(self):
        current_sigs = {
            "img_01.png": "sig_01",  # reused
            "img_04.png": "sig_04",  # new
        }
        plan = build_incremental_plan(self.old_meta, current_sigs)

        new_samples = [
            _nested_sample(
                "00004",
                "img_04.png",
                "sig_04",
                yaw="center",
                sharpness=300.0,
                exposure=0.99,
            )
        ]

        final_samples, summary = reconcile_and_finalize_samples(plan, new_samples)

        self.assertEqual(len(final_samples), 2)
        self.assertEqual(set(summary.keys()), set(CANONICAL_SUMMARY_KEYS))
        self.assertEqual(summary["total_samples"], 2)
        self.assertEqual(summary["valid_samples"], 2)
        self.assertEqual(summary["invalid_samples"], 0)
        self.assertEqual(summary["yaw_bucket_counts"]["center"], 2)
        self.assertIn("normalization", summary)
        self.assertIn("quality_stats", summary)
        # Old legacy keys must not reappear.
        self.assertNotIn("pose_distribution_yaw", summary)
        self.assertIn("usable_pose_samples", summary)
        self.assertIn("valid_image_samples", summary)
        # Ticket 14 legacy summary keys must not reappear as top-level distributions.
        self.assertNotIn("pose_distribution_yaw", summary)
        self.assertNotIn("quality_normalization", summary)

        for s in final_samples:
            self.assertIn("quality", s)
            self.assertIn("quality_score", s["quality"])
            self.assertTrue(0.0 <= s["quality"]["quality_score"] <= 1.0)
            self.assertIn("pose", s)
            self.assertIn("yaw_bucket", s["pose"])

    def test_reconcile_promotes_legacy_flat_pose(self):
        """Legacy flat pose fields on reused records still feed canonical counts."""
        plan = IncrementalPlan(
            is_incremental=True,
            reused_sample_keys=["legacy.png"],
            reused_sample_records={
                "legacy.png": {
                    "sample_id": "00009",
                    "sample_key": "legacy.png",
                    "signature": "sig_legacy",
                    "valid": True,
                    "pose_bucket_yaw": "center",
                    "pose_bucket_pitch": "level",
                    "quality_raw": {
                        "valid": True,
                        "sharpness_raw": 120.0,
                        "exposure_score": 0.8,
                    },
                    "issues": [],
                }
            },
        )
        final_samples, summary = reconcile_and_finalize_samples(plan, [])
        self.assertEqual(summary["total_samples"], 1)
        self.assertEqual(summary["yaw_bucket_counts"]["center"], 1)
        self.assertEqual(final_samples[0]["pose"]["yaw_bucket"], "center")


if __name__ == "__main__":
    unittest.main()
