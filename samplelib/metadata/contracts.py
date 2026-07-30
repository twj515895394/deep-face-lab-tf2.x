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


# Allowed bool-compatible forms (shared by Schema and Loader):
# True / False, exact int 0 / 1, strings true/false/1/0 (case-insensitive, stripped).
# Explicitly rejected: other ints (2, -1), floats (1.0, 0.0), empty string, None, other strings.
_BOOL_TRUE_STRINGS = frozenset({"true", "1"})
_BOOL_FALSE_STRINGS = frozenset({"false", "0"})
_BOOL_COMPAT_STRINGS = _BOOL_TRUE_STRINGS | _BOOL_FALSE_STRINGS

# Analyzer writes pose/quality/image/landmarks; all present known children must be mappings.
KNOWN_RECORD_CHILD_KEYS: Tuple[str, ...] = ("pose", "quality", "image", "landmarks")


def is_bool_compatible(val: Any) -> bool:
    """
    Return True iff val is an accepted boolean-compatible encoding.
    Schema and Loader must share this rule (single contract).
    """
    if isinstance(val, bool):
        return True
    # Use type(val) is int so bool is not double-counted and float is rejected.
    if type(val) is int and val in (0, 1):
        return True
    if isinstance(val, str) and val.strip().lower() in _BOOL_COMPAT_STRINGS:
        return True
    return False


def parse_bool_valid(val: Any) -> bool:
    """
    Safely parse boolean validity value under the shared bool-compatible contract.
    Incompatible values (including 2, -1, 1.0, "", None) return False.
    Prevents Python string truthiness traps (e.g. bool("false") == True)
    and float equality traps (e.g. 1.0 == 1).
    """
    if isinstance(val, bool):
        return val
    if type(val) is int:
        if val == 1:
            return True
        if val == 0:
            return False
        return False
    if isinstance(val, str):
        val_clean = val.strip().lower()
        if val_clean in _BOOL_TRUE_STRINGS:
            return True
        if val_clean in _BOOL_FALSE_STRINGS:
            return False
    return False


def is_record_structurally_valid(record: Any) -> bool:
    """
    metadata_valid structural gate:
    - record is a mapping
    - at least one known child key (pose/quality/image/landmarks) is present
    - every present known child value is itself a mapping

    Business validity of pose/quality/image/landmarks remains separate.
    """
    if not isinstance(record, dict):
        return False
    present = 0
    for key in KNOWN_RECORD_CHILD_KEYS:
        if key not in record:
            continue
        present += 1
        if not isinstance(record.get(key), dict):
            return False
    return present > 0


# ---------------------------------------------------------------------------
# Common Sample Record Validity Accessors (Single Source of Truth)
# ---------------------------------------------------------------------------

def get_record_image_valid(record: dict) -> bool:
    if not isinstance(record, dict):
        return False
    img_info = record.get("image")
    if isinstance(img_info, dict):
        return parse_bool_valid(img_info.get("valid"))
    return False


def get_record_landmarks_valid(record: dict) -> bool:
    """landmarks.valid under the shared bool-compatible contract."""
    if not isinstance(record, dict):
        return False
    lm_info = record.get("landmarks")
    if isinstance(lm_info, dict):
        return parse_bool_valid(lm_info.get("valid"))
    return False


def get_record_pose_valid(record: dict) -> bool:
    if not isinstance(record, dict):
        return False
    pose_info = record.get("pose")
    if isinstance(pose_info, dict) and parse_bool_valid(pose_info.get("valid")):
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


def get_record_usable_for_pose(record: dict) -> bool:
    """Image valid + pose business-valid (canonical yaw)."""
    return get_record_image_valid(record) and get_record_pose_valid(record)


def get_record_usable_for_quality(record: dict) -> bool:
    """Image valid + finite quality_score."""
    return get_record_image_valid(record) and get_record_quality_valid(record)


_HARD_INVALID_ISSUE_MARKERS = (
    "IMAGE_",
    "DECODE",
    "SIGNATURE_",
    "IDENTITY_",
    "LOAD_ERROR",
    "READ_ERROR",
    "NO_RAW",
    "WORKER_",
)


def is_record_summary_invalid(record: dict) -> bool:
    """
    Overall invalid for Analyzer summary (Ticket 18).

    - image invalid → invalid
    - identity/signature/load hard issues → invalid
    - pose-only / quality-low alone → NOT overall invalid
    """
    if not isinstance(record, dict):
        return True
    if not get_record_image_valid(record):
        return True
    for issue in (record.get("issues") or []):
        s = str(issue).upper()
        if any(m in s for m in _HARD_INVALID_ISSUE_MARKERS):
            return True
    return False
