"""
Ticket 14/17/18: shared canonical summary builder for full and incremental Analyzer paths.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from samplelib.metadata.contracts import (
    PITCH_BUCKET_NAMES,
    YAW_BUCKET_NAMES,
    get_record_image_valid,
    get_record_pitch_bucket,
    get_record_pose_valid,
    get_record_quality_valid,
    get_record_usable_for_pose,
    get_record_usable_for_quality,
    get_record_yaw_bucket,
    is_record_summary_invalid,
)

# Ticket 18 summary contract (includes Ticket 14 core keys as aliases).
CANONICAL_SUMMARY_KEYS = (
    "total_samples",
    "valid_samples",  # alias: total - invalid_samples
    "valid_image_samples",
    "valid_pose_samples",
    "valid_quality_samples",
    "usable_pose_samples",
    "usable_quality_samples",
    "invalid_samples",
    "yaw_bucket_counts",
    "pitch_bucket_counts",
    "unknown_yaw_count",
    "unknown_pitch_count",
    "quality_stats",
    "normalization",
)


def extract_pose_buckets(sample: dict) -> Tuple[str, str]:
    """
    Canonical yaw/pitch via Ticket 14 accessors, with legacy flat fallback.
    """
    if not isinstance(sample, dict):
        return "unknown", "unknown"

    y_name, _, y_ok = get_record_yaw_bucket(sample)
    p_name, _, p_ok = get_record_pitch_bucket(sample)
    if y_ok or p_ok or isinstance(sample.get("pose"), dict):
        return str(y_name or "unknown"), str(p_name or "unknown")

    # Legacy flat fields (pre-Ticket 14) — only when nested pose is missing.
    y_legacy = sample.get("pose_bucket_yaw")
    p_legacy = sample.get("pose_bucket_pitch")
    return str(y_legacy or "unknown"), str(p_legacy or "unknown")


def sample_has_issues(sample: dict) -> bool:
    if not isinstance(sample, dict):
        return True
    return bool(sample.get("issues") or [])


def build_canonical_summary(
    finalized_samples: Sequence[dict],
    norm_summary: Optional[Dict[str, Any]] = None,
    *,
    samples_len: Optional[int] = None,
    invalid_count: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Build Ticket 18 canonical summary from finalized sample records.

    Full and incremental Analyzer paths must both call this so summary key set,
    nested bucket counts, quality_stats, and normalization stay aligned.
    """
    samples_list: List[dict] = list(finalized_samples or [])
    if samples_len is None:
        samples_len = len(samples_list)

    yaw_counts = {b: 0 for b in YAW_BUCKET_NAMES}
    yaw_counts["unknown"] = 0
    pitch_counts = {b: 0 for b in PITCH_BUCKET_NAMES}
    pitch_counts["unknown"] = 0
    valid_quality_scores: List[float] = []

    valid_image = 0
    valid_pose = 0
    valid_quality = 0
    usable_pose = 0
    usable_quality = 0
    computed_invalid = 0
    unknown_yaw = 0
    unknown_pitch = 0

    for s in samples_list:
        y_name, _, y_ok = get_record_yaw_bucket(s)
        p_name, _, p_ok = get_record_pitch_bucket(s)
        # Prefer accessor names; fall back to extract for legacy flat records.
        if not isinstance(s.get("pose"), dict):
            y_name, p_name = extract_pose_buckets(s)
            y_ok = y_name in YAW_BUCKET_NAMES
            p_ok = p_name in PITCH_BUCKET_NAMES

        yaw_counts[y_name] = yaw_counts.get(y_name, 0) + 1
        pitch_counts[p_name] = pitch_counts.get(p_name, 0) + 1
        if (not y_ok) or y_name == "unknown" or y_name not in YAW_BUCKET_NAMES:
            unknown_yaw += 1
        if (not p_ok) or p_name == "unknown" or p_name not in PITCH_BUCKET_NAMES:
            unknown_pitch += 1

        if get_record_image_valid(s):
            valid_image += 1
        if get_record_pose_valid(s):
            valid_pose += 1
        if get_record_quality_valid(s):
            valid_quality += 1
            q_val = (s.get("quality") or {}).get("quality_score")
            try:
                qf = float(q_val)
                if math.isfinite(qf):
                    valid_quality_scores.append(qf)
            except (TypeError, ValueError):
                pass
        if get_record_usable_for_pose(s):
            usable_pose += 1
        if get_record_usable_for_quality(s):
            usable_quality += 1
        if is_record_summary_invalid(s):
            computed_invalid += 1

    if invalid_count is None:
        invalid_count = computed_invalid

    if len(valid_quality_scores) > 0:
        q_stats = {
            "min": float(np.min(valid_quality_scores)),
            "p05": float(np.percentile(valid_quality_scores, 5)),
            "median": float(np.median(valid_quality_scores)),
            "p95": float(np.percentile(valid_quality_scores, 95)),
            "max": float(np.max(valid_quality_scores)),
        }
    else:
        q_stats = {"min": 0.5, "p05": 0.5, "median": 0.5, "p95": 0.5, "max": 0.5}

    total = int(samples_len)
    inv = int(invalid_count)
    return {
        "total_samples": total,
        # Ticket 14 alias: samples that are not overall-invalid.
        "valid_samples": max(0, total - inv),
        "valid_image_samples": int(valid_image),
        "valid_pose_samples": int(valid_pose),
        "valid_quality_samples": int(valid_quality),
        "usable_pose_samples": int(usable_pose),
        "usable_quality_samples": int(usable_quality),
        "invalid_samples": inv,
        "yaw_bucket_counts": yaw_counts,
        "pitch_bucket_counts": pitch_counts,
        "unknown_yaw_count": int(unknown_yaw),
        "unknown_pitch_count": int(unknown_pitch),
        "quality_stats": q_stats,
        "normalization": dict(norm_summary or {}),
    }
