import sys
import unittest
from pathlib import Path

import numpy as np

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from samplelib.metadata.contracts import (
    LEGACY_PITCH_ALIASES,
    LEGACY_YAW_ALIASES,
    PITCH_BUCKET_NAME_TO_ID,
    PITCH_BUCKET_NAMES,
    UNKNOWN_BUCKET_ID,
    YAW_BUCKET_NAME_TO_ID,
    YAW_BUCKET_NAMES,
    get_pitch_bucket_id,
    get_yaw_bucket_id,
    is_valid_pitch_bucket,
    is_valid_yaw_bucket,
    normalize_pitch_bucket_name,
    normalize_yaw_bucket_name,
)
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
        """Verify yaw angle to bucket mapping at interior points."""
        self.assertEqual(assign_yaw_bucket(-0.9), "extreme_left")
        self.assertEqual(assign_yaw_bucket(-0.5), "major_left")
        self.assertEqual(assign_yaw_bucket(-0.2), "minor_left")
        self.assertEqual(assign_yaw_bucket(0.0), "center")
        self.assertEqual(assign_yaw_bucket(0.2), "minor_right")
        self.assertEqual(assign_yaw_bucket(0.5), "major_right")
        self.assertEqual(assign_yaw_bucket(0.9), "extreme_right")

    def test_assign_yaw_bucket_exact_thresholds(self):
        """Ticket 14: exact yaw thresholds -0.8/-0.4/-0.15/0.15/0.4/0.8."""
        # yaw < -0.8 -> extreme_left; at -0.8 falls into major_left
        self.assertEqual(assign_yaw_bucket(-0.8000001), "extreme_left")
        self.assertEqual(assign_yaw_bucket(-0.8), "major_left")
        self.assertEqual(assign_yaw_bucket(-0.4), "minor_left")
        self.assertEqual(assign_yaw_bucket(-0.15), "center")
        self.assertEqual(assign_yaw_bucket(0.15), "center")
        self.assertEqual(assign_yaw_bucket(0.4), "minor_right")
        self.assertEqual(assign_yaw_bucket(0.8), "major_right")
        self.assertEqual(assign_yaw_bucket(0.8000001), "extreme_right")

    def test_assign_yaw_left_right_not_inverted(self):
        """Left is negative yaw, right is positive yaw — never inverted."""
        self.assertIn("left", assign_yaw_bucket(-0.9))
        self.assertIn("right", assign_yaw_bucket(0.9))
        self.assertNotIn("right", assign_yaw_bucket(-0.5))
        self.assertNotIn("left", assign_yaw_bucket(0.5))

    def test_canonical_yaw_pitch_sets_complete(self):
        """Canonical 7 yaw / 3 pitch sets and fixed ID tables."""
        self.assertEqual(len(YAW_BUCKET_NAMES), 7)
        self.assertEqual(len(PITCH_BUCKET_NAMES), 3)
        self.assertEqual(set(YAW_BUCKET_NAME_TO_ID.keys()), set(YAW_BUCKET_NAMES))
        self.assertEqual(set(PITCH_BUCKET_NAME_TO_ID.keys()), set(PITCH_BUCKET_NAMES))
        self.assertEqual(
            [YAW_BUCKET_NAME_TO_ID[n] for n in YAW_BUCKET_NAMES],
            list(range(7)),
        )
        self.assertEqual(
            [PITCH_BUCKET_NAME_TO_ID[n] for n in PITCH_BUCKET_NAMES],
            list(range(3)),
        )

    def test_assign_pitch_bucket_boundaries(self):
        """Verify pitch angle to bucket mapping boundaries."""
        self.assertEqual(assign_pitch_bucket(-0.3), "up")
        self.assertEqual(assign_pitch_bucket(0.0), "level")
        self.assertEqual(assign_pitch_bucket(0.3), "down")

    def test_assign_pitch_bucket_exact_thresholds(self):
        """Ticket 14: exact pitch thresholds -0.15 / 0.15."""
        self.assertEqual(assign_pitch_bucket(-0.1500001), "up")
        self.assertEqual(assign_pitch_bucket(-0.15), "level")
        self.assertEqual(assign_pitch_bucket(0.15), "level")
        self.assertEqual(assign_pitch_bucket(0.1500001), "down")

    def test_contracts_alias_extreme_and_invalid_inputs(self):
        """contracts: alias, extreme, None, numbers, empty/unknown strings."""
        for alias, canonical in LEGACY_YAW_ALIASES.items():
            name, ok = normalize_yaw_bucket_name(alias)
            self.assertTrue(ok, alias)
            self.assertEqual(name, canonical)
            self.assertTrue(is_valid_yaw_bucket(alias))

        for alias, canonical in LEGACY_PITCH_ALIASES.items():
            name, ok = normalize_pitch_bucket_name(alias)
            self.assertTrue(ok, alias)
            self.assertEqual(name, canonical)
            self.assertTrue(is_valid_pitch_bucket(alias))

        # undirected extreme is unknown — must not invent left/right
        name, ok = normalize_yaw_bucket_name("extreme")
        self.assertFalse(ok)
        self.assertEqual(name, "unknown")
        y_id, y_ok = get_yaw_bucket_id("extreme")
        self.assertFalse(y_ok)
        self.assertEqual(y_id, UNKNOWN_BUCKET_ID)

        for bad in (None, 3, 1.5, "", "  ", "totally_unknown_bucket"):
            y_name, y_ok = normalize_yaw_bucket_name(bad)
            p_name, p_ok = normalize_pitch_bucket_name(bad)
            self.assertFalse(y_ok, bad)
            self.assertFalse(p_ok, bad)
            self.assertEqual(y_name, "unknown")
            self.assertEqual(p_name, "unknown")

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
