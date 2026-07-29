"""
Single Source of Truth for Faceset Metadata Contracts.
Defines canonical pose bucket names, IDs, legacy aliases, and record validation accessors.
"""

from typing import Any, Dict, Optional, Tuple

YAW_BUCKET_NAMES: Tuple[str, ...] = (
    "extreme_left",
    "major_left",
    "minor_left",
    "center",
    "minor_right",
    "major_right",
    "extreme_right",
)

PITCH_BUCKET_NAMES: Tuple[str, ...] = (
    "up",
    "level",
    "down",
)

YAW_BUCKET_NAME_TO_ID: Dict[str, int] = {
    "extreme_left": 0,
    "major_left": 1,
    "minor_left": 2,
    "center": 3,
    "minor_right": 4,
    "major_right": 5,
    "extreme_right": 6,
}

PITCH_BUCKET_NAME_TO_ID: Dict[str, int] = {
    "up": 0,
    "level": 1,
    "down": 2,
}

UNKNOWN_BUCKET_ID: int = -1

# Backward compatibility mappings for legacy sidecar metadata files
LEGACY_YAW_ALIASES: Dict[str, str] = {
    "front": "center",
    "pitch_center_yaw_center": "center",
    "slight_left": "minor_left",
    "slight_right": "minor_right",
    "left": "major_left",
    "right": "major_right",
}

LEGACY_PITCH_ALIASES: Dict[str, str] = {
    "center": "level",
}


def normalize_yaw_bucket_name(name: Optional[Any]) -> Tuple[str, bool]:
    """
    Normalize yaw bucket string to canonical name.
    Returns (canonical_name, is_valid).
    """
    if not isinstance(name, str) or not name:
        return "unknown", False

    name_clean = name.strip()
    if name_clean in YAW_BUCKET_NAME_TO_ID:
        return name_clean, True

    if name_clean in LEGACY_YAW_ALIASES:
        return LEGACY_YAW_ALIASES[name_clean], True

    return "unknown", False


def normalize_pitch_bucket_name(name: Optional[Any]) -> Tuple[str, bool]:
    """
    Normalize pitch bucket string to canonical name.
    Returns (canonical_name, is_valid).
    """
    if not isinstance(name, str) or not name:
        return "unknown", False

    name_clean = name.strip()
    if name_clean in PITCH_BUCKET_NAME_TO_ID:
        return name_clean, True

    if name_clean in LEGACY_PITCH_ALIASES:
        return LEGACY_PITCH_ALIASES[name_clean], True

    return "unknown", False


def get_yaw_bucket_id(name: Optional[Any]) -> Tuple[int, bool]:
    """
    Map yaw bucket string to integer bucket ID (0..6).
    Returns (bucket_id, is_valid). Invalid/Unknown maps to (UNKNOWN_BUCKET_ID, False).
    """
    norm_name, is_valid = normalize_yaw_bucket_name(name)
    if is_valid:
        return YAW_BUCKET_NAME_TO_ID[norm_name], True
    return UNKNOWN_BUCKET_ID, False


def get_pitch_bucket_id(name: Optional[Any]) -> Tuple[int, bool]:
    """
    Map pitch bucket string to integer bucket ID (0..2).
    Returns (bucket_id, is_valid). Invalid/Unknown maps to (UNKNOWN_BUCKET_ID, False).
    """
    norm_name, is_valid = normalize_pitch_bucket_name(name)
    if is_valid:
        return PITCH_BUCKET_NAME_TO_ID[norm_name], True
    return UNKNOWN_BUCKET_ID, False


def is_valid_yaw_bucket(name: Optional[Any]) -> bool:
    _, is_valid = normalize_yaw_bucket_name(name)
    return is_valid


def is_valid_pitch_bucket(name: Optional[Any]) -> bool:
    _, is_valid = normalize_pitch_bucket_name(name)
    return is_valid


# ---------------------------------------------------------------------------
# Common Sample Record Validity Accessors (Single Source of Truth)
# ---------------------------------------------------------------------------

def get_record_image_valid(record: dict) -> bool:
    if not isinstance(record, dict):
        return False
    img_info = record.get("image")
    if isinstance(img_info, dict):
        return bool(img_info.get("valid", False))
    return False


def get_record_pose_valid(record: dict) -> bool:
    if not isinstance(record, dict):
        return False
    pose_info = record.get("pose")
    if isinstance(pose_info, dict) and bool(pose_info.get("valid", False)):
        yaw_str = pose_info.get("yaw_bucket")
        _, is_valid = get_yaw_bucket_id(yaw_str)
        return is_valid
    return False


def get_record_quality_valid(record: dict) -> bool:
    if not isinstance(record, dict):
        return False
    q_info = record.get("quality")
    if isinstance(q_info, dict):
        q_score = q_info.get("quality_score")
        if q_score is not None:
            try:
                val = float(q_score)
                import math
                return math.isfinite(val)
            except (ValueError, TypeError):
                return False
    return False


def get_record_yaw_bucket(record: dict) -> Tuple[str, int, bool]:
    if not isinstance(record, dict):
        return "unknown", UNKNOWN_BUCKET_ID, False
    pose_info = record.get("pose")
    if isinstance(pose_info, dict):
        yaw_str = pose_info.get("yaw_bucket")
        norm_name, is_valid = normalize_yaw_bucket_name(yaw_str)
        b_id, _ = get_yaw_bucket_id(yaw_str)
        return norm_name, b_id, is_valid
    return "unknown", UNKNOWN_BUCKET_ID, False


def get_record_pitch_bucket(record: dict) -> Tuple[str, int, bool]:
    if not isinstance(record, dict):
        return "unknown", UNKNOWN_BUCKET_ID, False
    pose_info = record.get("pose")
    if isinstance(pose_info, dict):
        pitch_str = pose_info.get("pitch_bucket")
        norm_name, is_valid = normalize_pitch_bucket_name(pitch_str)
        b_id, _ = get_pitch_bucket_id(pitch_str)
        return norm_name, b_id, is_valid
    return "unknown", UNKNOWN_BUCKET_ID, False
