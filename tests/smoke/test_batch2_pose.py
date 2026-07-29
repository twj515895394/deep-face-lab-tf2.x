import sys
import unittest
from pathlib import Path

import numpy as np

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from samplelib.metadata.pose import (
    FacesetPoseConfig,
    analyze_pose,
    assign_pitch_bucket,
    assign_yaw_bucket,
    validate_landmarks,
)
from tests.fixtures.batch2.build_synthetic_fixture import generate_synthetic_landmarks


class TestBatch2Pose(unittest.TestCase):
    def test_validate_landmarks_valid_and_invalid(self):
        """Test landmark array validation rules."""
        valid_lm = generate_synthetic_landmarks("center")
        val1 = validate_landmarks(valid_lm)
        self.assertTrue(val1.valid)
        self.assertEqual(val1.point_count, 68)

        # Missing / None
        self.assertFalse(validate_landmarks(None).valid)

        # Wrong shape
        wrong_shape = np.zeros((60, 2), dtype=np.float32)
        self.assertFalse(validate_landmarks(wrong_shape).valid)

        # Non-finite (NaN)
        nan_lm = valid_lm.copy()
        nan_lm[0, 0] = np.nan
        self.assertFalse(validate_landmarks(nan_lm).valid)

    def test_assign_yaw_bucket_boundaries(self):
        """Verify yaw angle to bucket mapping boundaries."""
        self.assertEqual(assign_yaw_bucket(-0.9), "extreme_left")
        self.assertEqual(assign_yaw_bucket(-0.5), "major_left")
        self.assertEqual(assign_yaw_bucket(-0.2), "minor_left")
        self.assertEqual(assign_yaw_bucket(0.0), "center")
        self.assertEqual(assign_yaw_bucket(0.2), "minor_right")
        self.assertEqual(assign_yaw_bucket(0.5), "major_right")
        self.assertEqual(assign_yaw_bucket(0.9), "extreme_right")

    def test_assign_pitch_bucket_boundaries(self):
        """Verify pitch angle to bucket mapping boundaries."""
        self.assertEqual(assign_pitch_bucket(-0.3), "up")
        self.assertEqual(assign_pitch_bucket(0.0), "level")
        self.assertEqual(assign_pitch_bucket(0.3), "down")

    def test_analyze_pose_center_left_right(self):
        """Verify analyze_pose on synthetic landmarks."""
        lm_center = generate_synthetic_landmarks("center")
        res_center = analyze_pose(lm_center, img_shape=(256, 256, 3))
        self.assertTrue(res_center.valid)
        self.assertIsNotNone(res_center.yaw)
        self.assertIsNotNone(res_center.pitch)
        self.assertIsNotNone(res_center.roll)

        lm_left = generate_synthetic_landmarks("left_yaw")
        res_left = analyze_pose(lm_left, img_shape=(256, 256, 3))
        self.assertTrue(res_left.valid)

        lm_right = generate_synthetic_landmarks("right_yaw")
        res_right = analyze_pose(lm_right, img_shape=(256, 256, 3))
        self.assertTrue(res_right.valid)


if __name__ == "__main__":
    unittest.main()
