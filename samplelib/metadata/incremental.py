import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from samplelib.metadata.quality import FacesetQualityConfig, finalize_quality_scores
from samplelib.metadata.schema import SCHEMA_VERSION_CURRENT, FacesetMetadataV1
from samplelib.metadata.summary_builder import build_canonical_summary


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
    current_signature_mode: str = "quick",
) -> IncrementalPlan:
    """
    Build an incremental plan by comparing existing metadata with current sample signatures.

    Args:
        old_metadata: Previous FacesetMetadataV1 instance (if any).
        current_signatures: Mapping sample_key -> signature dict.
        analyzer_version: Current analyzer version string.
        force: If True, bypass incremental reuse and force full analysis.
        current_signature_mode: "quick" or "strong" for this run.

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

    from samplelib.metadata.fingerprint import (
        SIGNATURE_MODE_QUICK,
        SIGNATURE_MODE_STRONG,
        signature_mode_from_analysis_config,
        signatures_match,
        SampleSignature,
    )

    old_mode = signature_mode_from_analysis_config(getattr(old_metadata, "analysis_config", None))
    cur_mode = (current_signature_mode or SIGNATURE_MODE_QUICK).lower()

    # strong -> quick: never degrade. CLI must refuse (non-zero) and keep Sidecar.
    if old_mode == SIGNATURE_MODE_STRONG and cur_mode == SIGNATURE_MODE_QUICK:
        return IncrementalPlan(
            is_incremental=False,
            reasons=["SIGNATURE_MODE_DOWNGRADE_FORBIDDEN_STRONG_TO_QUICK"],
        )

    # quick -> strong: require re-sign / full recompute (safe default).
    if old_mode == SIGNATURE_MODE_QUICK and cur_mode == SIGNATURE_MODE_STRONG:
        return IncrementalPlan(
            is_incremental=False,
            added_sample_keys=list(current_signatures.keys()),
            reasons=["SIGNATURE_MODE_UPGRADE_TO_STRONG_REQUIRES_RECOMPUTE"],
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
            # Prefer structured match so optional new hash fields compare correctly.
            matched = False
            if isinstance(current_sig, dict):
                try:
                    cur_obj = SampleSignature.from_dict(current_sig)
                    matched = signatures_match(old_sig, cur_obj, mode=cur_mode)
                except Exception:
                    matched = bool(old_sig and old_sig == current_sig)
            else:
                matched = bool(old_sig and old_sig == current_sig)

            if matched:
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
            f"SIGNATURE_MODE_{cur_mode}",
        ],
        reused_sample_records=reused_records,
    )


def reconcile_and_finalize_samples(
    plan: IncrementalPlan,
    new_analyzed_samples: List[dict],
    quality_config: Optional[FacesetQualityConfig] = None,
) -> Tuple[List[dict], dict]:
    """
    Reconcile reused sample records and newly analyzed sample records.
    Re-runs Pass 2 robust percentile quality normalization across the entire faceset
    and builds the same Ticket 14 canonical summary as full Analyzer.

    Returns:
        (final_samples_list, summary_dict)
    """
    raw_combined: List[dict] = []

    # 1. Add reused records (deep copy so Pass 2 cannot mutate plan/old sidecar objects)
    for key in plan.reused_sample_keys:
        rec = copy.deepcopy(plan.reused_sample_records[key])
        if "quality_raw" not in rec and "quality" in rec:
            q_old = rec["quality"] if isinstance(rec.get("quality"), dict) else {}
            # Nested image.valid preferred; legacy top-level valid is fallback only.
            image_info = rec.get("image") if isinstance(rec.get("image"), dict) else {}
            rec["quality_raw"] = {
                "valid": bool(image_info.get("valid", rec.get("valid", True))),
                "sharpness_raw": q_old.get("sharpness_raw"),
                "dark_ratio": q_old.get("dark_ratio"),
                "bright_ratio": q_old.get("bright_ratio"),
                "exposure_score": q_old.get("exposure_score"),
            }
        # Promote legacy flat pose fields into nested contract when reusing old records.
        if not isinstance(rec.get("pose"), dict):
            y_b = rec.get("pose_bucket_yaw")
            p_b = rec.get("pose_bucket_pitch")
            if y_b is not None or p_b is not None:
                rec["pose"] = {
                    "valid": bool(rec.get("valid", True)),
                    "yaw_bucket": y_b or "unknown",
                    "pitch_bucket": p_b or "unknown",
                }
        raw_combined.append(rec)

    # 2. Add newly analyzed sample records (also deep-copied for isolation)
    for rec in new_analyzed_samples:
        raw_combined.append(copy.deepcopy(rec) if isinstance(rec, dict) else rec)

    # Duplicate sample_key / sample_id is a validation failure (Ticket 18).
    seen_keys = set()
    seen_ids = set()
    for rec in raw_combined:
        if not isinstance(rec, dict):
            continue
        sk = rec.get("sample_key")
        sid = rec.get("sample_id")
        if sk is not None:
            if sk in seen_keys:
                raise ValueError(f"Duplicate sample_key in incremental reconcile: {sk}")
            seen_keys.add(sk)
        if sid is not None:
            if sid in seen_ids:
                raise ValueError(f"Duplicate sample_id in incremental reconcile: {sid}")
            seen_ids.add(sid)

    # Sort samples consistently by sample_id
    raw_combined.sort(key=lambda s: str(s.get("sample_id", s.get("sample_key", ""))))

    # 3. Re-run Pass 2 quality normalization across the full faceset
    finalized_samples, norm_summary = finalize_quality_scores(raw_combined, quality_config)

    # 4. Same canonical summary builder as full Analyzer (Ticket 18).
    overall_summary = build_canonical_summary(
        finalized_samples,
        norm_summary,
        samples_len=len(finalized_samples),
    )

    return finalized_samples, overall_summary
