"""
Ticket 14/17: shared canonical summary builder for full and incremental Analyzer paths.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from samplelib.metadata.contracts import PITCH_BUCKET_NAMES, YAW_BUCKET_NAMES

# Ticket 14 frozen top-level summary keys (must match full Analyzer output).
CANONICAL_SUMMARY_KEYS = (
    "total_samples",
    "valid_samples",
    "invalid_samples",
    "yaw_bucket_counts",
    "pitch_bucket_counts",
    "quality_stats",
    "normalization",
)


def extract_pose_buckets(sample: dict) -> Tuple[str, str]:
    """
    Read yaw/pitch buckets from nested pose contract, with legacy top-level fallback.
    """
    if not isinstance(sample, dict):
        return "unknown", "unknown"

    pose = sample.get("pose")
    if isinstance(pose, dict):
        y_b = pose.get("yaw_bucket")
        p_b = pose.get("pitch_bucket")
        if y_b is not None or p_b is not None:
            return str(y_b or "unknown"), str(p_b or "unknown")

    # Legacy flat fields (pre-Ticket 14) — only used when reusing very old records.
    y_legacy = sample.get("pose_bucket_yaw")
    p_legacy = sample.get("pose_bucket_pitch")
    return str(y_legacy or "unknown"), str(p_legacy or "unknown")


def sample_has_issues(sample: dict) -> bool:
    if not isinstance(sample, dict):
        return True
    issues = sample.get("issues") or []
    return bool(issues)


def build_canonical_summary(
    finalized_samples: Sequence[dict],
    norm_summary: Optional[Dict[str, Any]] = None,
    *,
    samples_len: Optional[int] = None,
    invalid_count: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Build Ticket 14 canonical summary from finalized sample records.

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

    computed_invalid = 0
    for s in samples_list:
        y_b, p_b = extract_pose_buckets(s)
        yaw_counts[y_b] = yaw_counts.get(y_b, 0) + 1
        pitch_counts[p_b] = pitch_counts.get(p_b, 0) + 1

        quality = s.get("quality") if isinstance(s.get("quality"), dict) else {}
        q_val = quality.get("quality_score")
        if q_val is not None:
            try:
                qf = float(q_val)
                if math.isfinite(qf):
                    valid_quality_scores.append(qf)
            except (TypeError, ValueError):
                pass

        if sample_has_issues(s):
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

    return {
        "total_samples": int(samples_len),
        "valid_samples": int(samples_len) - int(invalid_count),
        "invalid_samples": int(invalid_count),
        "yaw_bucket_counts": yaw_counts,
        "pitch_bucket_counts": pitch_counts,
        "quality_stats": q_stats,
        "normalization": dict(norm_summary or {}),
    }
