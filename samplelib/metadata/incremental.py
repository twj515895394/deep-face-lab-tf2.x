from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from samplelib.metadata.quality import finalize_quality_scores
from samplelib.metadata.schema import SCHEMA_VERSION_CURRENT, FacesetMetadataV1


@dataclass
class IncrementalPlan:
    is_incremental: bool
    reused_sample_keys: List[str] = field(default_factory=list)
    recompute_sample_keys: List[str] = field(default_factory=list)
    added_sample_keys: List[str] = field(default_factory=list)
    removed_sample_keys: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    reused_sample_records: Dict[str, dict] = field(default_factory=dict)


def build_incremental_plan(
    old_metadata: Optional[FacesetMetadataV1],
    current_signatures: Dict[str, str],
    analyzer_version: str = "v1.0",
    force: bool = False,
) -> IncrementalPlan:
    """
    Build an incremental plan by comparing existing metadata with current sample signatures.

    Args:
        old_metadata: Previous FacesetMetadataV1 instance (if any).
        current_signatures: Mapping sample_key -> signature (MD5/sha256/mtime).
        analyzer_version: Current analyzer version string.
        force: If True, bypass incremental reuse and force full analysis.

    Returns:
        IncrementalPlan object describing reused, recomputed, added, and removed samples.
    """
    if force:
        return IncrementalPlan(
            is_incremental=False,
            added_sample_keys=list(current_signatures.keys()),
            reasons=["FORCED_FULL_ANALYSIS"],
        )

    if not old_metadata:
        return IncrementalPlan(
            is_incremental=False,
            added_sample_keys=list(current_signatures.keys()),
            reasons=["NO_PREVIOUS_METADATA"],
        )

    if old_metadata.schema_version != SCHEMA_VERSION_CURRENT:
        return IncrementalPlan(
            is_incremental=False,
            added_sample_keys=list(current_signatures.keys()),
            reasons=[f"UNSUPPORTED_SCHEMA_VERSION_{old_metadata.schema_version}"],
        )

    if old_metadata.analyzer_version != analyzer_version:
        return IncrementalPlan(
            is_incremental=False,
            added_sample_keys=list(current_signatures.keys()),
            reasons=[f"ANALYZER_VERSION_CHANGED_{old_metadata.analyzer_version}_TO_{analyzer_version}"],
        )

    old_dict = {s.get("sample_key"): s for s in old_metadata.samples if isinstance(s, dict) and "sample_key" in s}

    reused_keys = []
    recompute_keys = []
    added_keys = []
    reused_records = {}

    for key, current_sig in current_signatures.items():
        if key in old_dict:
            old_rec = old_dict[key]
            old_sig = old_rec.get("signature")
            if old_sig and old_sig == current_sig:
                reused_keys.append(key)
                reused_records[key] = old_rec
            else:
                recompute_keys.append(key)
        else:
            added_keys.append(key)

    removed_keys = [k for k in old_dict.keys() if k not in current_signatures]

    return IncrementalPlan(
        is_incremental=True,
        reused_sample_keys=reused_keys,
        recompute_sample_keys=recompute_keys,
        added_sample_keys=added_keys,
        removed_sample_keys=removed_keys,
        reasons=[
            f"REUSED_{len(reused_keys)}",
            f"RECOMPUTE_{len(recompute_keys)}",
            f"ADDED_{len(added_keys)}",
            f"REMOVED_{len(removed_keys)}",
        ],
        reused_sample_records=reused_records,
    )


def reconcile_and_finalize_samples(
    plan: IncrementalPlan,
    new_analyzed_samples: List[dict],
) -> Tuple[List[dict], dict]:
    """
    Reconcile reused sample records and newly analyzed sample records.
    Re-runs Pass 2 robust percentile quality normalization across the entire faceset
    and computes full dataset summary.

    Returns:
        (final_samples_list, summary_dict)
    """
    raw_combined: List[dict] = []

    # 1. Add reused records (ensure quality_raw is intact or constructable from legacy fields)
    for key in plan.reused_sample_keys:
        rec = dict(plan.reused_sample_records[key])
        if "quality_raw" not in rec and "quality" in rec:
            q_old = rec["quality"]
            rec["quality_raw"] = {
                "valid": rec.get("valid", True),
                "sharpness_raw": q_old.get("sharpness_raw"),
                "dark_ratio": q_old.get("dark_ratio"),
                "bright_ratio": q_old.get("bright_ratio"),
                "exposure_score": q_old.get("exposure_score"),
            }
        raw_combined.append(rec)

    # 2. Add newly analyzed sample records
    raw_combined.extend(new_analyzed_samples)

    # Sort samples consistently by sample_id
    raw_combined.sort(key=lambda s: str(s.get("sample_id", s.get("sample_key", ""))))

    # 3. Re-run Pass 2 quality normalization
    finalized_samples, norm_summary = finalize_quality_scores(raw_combined)

    # 4. Generate overall summary
    yaw_buckets = {b: 0 for b in ["pitch_center_yaw_center", "front", "slight_left", "slight_right", "left", "right", "extreme"]}
    pitch_buckets = {b: 0 for b in ["up", "center", "down"]}
    total_valid = 0
    total_invalid = 0
    usable_count = 0

    for s in finalized_samples:
        if s.get("valid", True):
            total_valid += 1
            if s.get("usable_for_sampling", True):
                usable_count += 1

            y_b = s.get("pose_bucket_yaw")
            if y_b in yaw_buckets:
                yaw_buckets[y_b] += 1

            p_b = s.get("pose_bucket_pitch")
            if p_b in pitch_buckets:
                pitch_buckets[p_b] += 1
        else:
            total_invalid += 1

    overall_summary = {
        "total_samples": len(finalized_samples),
        "valid_samples": total_valid,
        "invalid_samples": total_invalid,
        "usable_for_sampling": usable_count,
        "pose_distribution_yaw": yaw_buckets,
        "pose_distribution_pitch": pitch_buckets,
        "quality_normalization": norm_summary,
    }

    return finalized_samples, overall_summary
