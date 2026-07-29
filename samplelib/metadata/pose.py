import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from facelib import LandmarksProcessor


@dataclass
class LandmarkValidation:
    valid: bool
    point_count: int = 0
    issues: List[str] = field(default_factory=list)


@dataclass
class FacesetPoseConfig:
    # Yaw thresholds in radians: extreme_left < -0.8 < major_left < -0.4 < minor_left < -0.15 < center <= 0.15 < minor_right <= 0.4 < major_right <= 0.8 < extreme_right
    yaw_thresholds: Tuple[float, ...] = (-0.8, -0.4, -0.15, 0.15, 0.4, 0.8)
    # Pitch thresholds in radians: up < -0.15 <= level <= 0.15 < down
    pitch_thresholds: Tuple[float, ...] = (-0.15, 0.15)


@dataclass
class PoseAnalysisResult:
    valid: bool
    pitch: Optional[float] = None
    yaw: Optional[float] = None
    roll: Optional[float] = None
    yaw_bucket: str = "unknown"
    pitch_bucket: str = "unknown"
    issues: List[str] = field(default_factory=list)


def validate_landmarks(landmarks: Optional[np.ndarray], img_shape: Optional[Tuple[int, ...]] = None) -> LandmarkValidation:
    """
    Validate landmarks array for face pose estimation.
    Expects 2D array of shape (68, 2) with finite coordinate values.
    """
    if landmarks is None:
        return LandmarkValidation(valid=False, point_count=0, issues=["MISSING_LANDMARKS"])

    if not isinstance(landmarks, np.ndarray):
        return LandmarkValidation(valid=False, point_count=0, issues=["INVALID_LANDMARKS_TYPE"])

    if len(landmarks.shape) != 2 or landmarks.shape[1] != 2:
        return LandmarkValidation(
            valid=False,
            point_count=len(landmarks) if len(landmarks.shape) > 0 else 0,
            issues=[f"INVALID_LANDMARKS_SHAPE_{landmarks.shape}"]
        )

    point_count = landmarks.shape[0]
    if point_count != 68:
        return LandmarkValidation(valid=False, point_count=point_count, issues=[f"UNEXPECTED_POINT_COUNT_{point_count}"])

    if not np.isfinite(landmarks).all():
        return LandmarkValidation(valid=False, point_count=point_count, issues=["NON_FINITE_LANDMARKS"])

    # Optional boundary check if img_shape is provided
    if img_shape is not None and len(img_shape) >= 2:
        h, w = img_shape[0], img_shape[1]
        min_x, min_y = landmarks[:, 0].min(), landmarks[:, 1].min()
        max_x, max_y = landmarks[:, 0].max(), landmarks[:, 1].max()

        # Allow slight padding outside crop box, but flag extreme out-of-bounds (>2x size)
        if min_x < -w or min_y < -h or max_x > 2 * w or max_y > 2 * h:
            return LandmarkValidation(valid=False, point_count=point_count, issues=["OUT_OF_BOUNDS_LANDMARKS"])

    return LandmarkValidation(valid=True, point_count=point_count)


from samplelib.metadata.contracts import PITCH_BUCKET_NAMES, YAW_BUCKET_NAMES


def assign_yaw_bucket(yaw: float, thresholds: Tuple[float, ...] = (-0.8, -0.4, -0.15, 0.15, 0.4, 0.8)) -> str:
    """
    Map yaw angle (in radians) to human-interpretable pose bucket.
    Must strictly return one of YAW_BUCKET_NAMES.
    """
    if not math.isfinite(yaw):
        return "unknown"

    if len(thresholds) != 6:
        thresholds = (-0.8, -0.4, -0.15, 0.15, 0.4, 0.8)

    t1, t2, t3, t4, t5, t6 = thresholds
    if yaw < t1:
        return YAW_BUCKET_NAMES[0]  # extreme_left
    elif yaw < t2:
        return YAW_BUCKET_NAMES[1]  # major_left
    elif yaw < t3:
        return YAW_BUCKET_NAMES[2]  # minor_left
    elif yaw <= t4:
        return YAW_BUCKET_NAMES[3]  # center
    elif yaw <= t5:
        return YAW_BUCKET_NAMES[4]  # minor_right
    elif yaw <= t6:
        return YAW_BUCKET_NAMES[5]  # major_right
    else:
        return YAW_BUCKET_NAMES[6]  # extreme_right


def assign_pitch_bucket(pitch: float, thresholds: Tuple[float, ...] = (-0.15, 0.15)) -> str:
    """
    Map pitch angle (in radians) to human-interpretable pitch bucket.
    Must strictly return one of PITCH_BUCKET_NAMES.
    """
    if not math.isfinite(pitch):
        return "unknown"

    if len(thresholds) != 2:
        thresholds = (-0.15, 0.15)

    t1, t2 = thresholds
    if pitch < t1:
        return PITCH_BUCKET_NAMES[0]  # up
    elif pitch <= t2:
        return PITCH_BUCKET_NAMES[1]  # level
    else:
        return PITCH_BUCKET_NAMES[2]  # down



def analyze_pose(landmarks: Optional[np.ndarray], img_shape: Optional[Tuple[int, ...]] = None, config: Optional[FacesetPoseConfig] = None) -> PoseAnalysisResult:
    """
    Estimate head pose angles (pitch, yaw, roll) and assign discrete pose buckets.
    """
    if config is None:
        config = FacesetPoseConfig()

    lm_val = validate_landmarks(landmarks, img_shape)
    if not lm_val.valid:
        return PoseAnalysisResult(valid=False, issues=lm_val.issues)

    size = img_shape[1] if img_shape is not None and len(img_shape) >= 2 else 256

    try:
        pitch, yaw, roll = LandmarksProcessor.estimate_pitch_yaw_roll(landmarks, size=size)
        pitch = float(pitch)
        yaw = float(yaw)
        roll = float(roll)

        if not (math.isfinite(pitch) and math.isfinite(yaw) and math.isfinite(roll)):
            return PoseAnalysisResult(valid=False, issues=["NON_FINITE_POSE"])

        yaw_b = assign_yaw_bucket(yaw, config.yaw_thresholds)
        pitch_b = assign_pitch_bucket(pitch, config.pitch_thresholds)

        return PoseAnalysisResult(
            valid=True,
            pitch=pitch,
            yaw=yaw,
            roll=roll,
            yaw_bucket=yaw_b,
            pitch_bucket=pitch_b,
        )
    except Exception as e:
        return PoseAnalysisResult(valid=False, issues=[f"POSE_ESTIMATION_ERROR_{type(e).__name__}"])
