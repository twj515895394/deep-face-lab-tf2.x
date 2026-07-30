from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np

from samplelib.metadata.contracts import (
    LEGACY_PITCH_ALIASES,
    LEGACY_YAW_ALIASES,
    PITCH_BUCKET_NAME_TO_ID,
    UNKNOWN_BUCKET_ID,
    YAW_BUCKET_NAME_TO_ID,
    get_pitch_bucket_id,
    get_record_image_valid,
    get_record_landmarks_valid,
    get_record_pitch_bucket,
    get_record_pose_valid,
    get_record_quality_valid,
    get_record_yaw_bucket,
    get_yaw_bucket_id,
    is_record_structurally_valid,
)
from samplelib.metadata.fingerprint import (
    SIGNATURE_MODE_QUICK,
    build_dataset_fingerprint,
    build_signature_from_sample,
    signature_mode_from_analysis_config,
    signatures_match,
)
from samplelib.metadata.identity import build_sample_id, build_sample_key
from samplelib.metadata.schema import SCHEMA_VERSION_CURRENT, FacesetMetadataV1, MetadataValidationIssue
from samplelib.metadata.store import load_metadata


# Schema issue codes that must be surfaced as bounded RuntimeMetadata warnings.
_SCHEMA_WARNING_CODES = frozenset({
    "LEGACY_YAW_BUCKET_ALIAS",
    "LEGACY_PITCH_BUCKET_ALIAS",
    "INVALID_POSE_MAPPING",
    "INVALID_POSE_VALID_TYPE",
    "INVALID_YAW_BUCKET",
    "INVALID_PITCH_BUCKET",
})

_MAX_WARNING_EXAMPLES = 5
# Hard upper bound on RuntimeMetadata.warnings length (aggregated codes + match status).
_MAX_RUNTIME_WARNINGS = 32


def _aggregate_schema_issues_to_warnings(
    issues: Sequence[MetadataValidationIssue],
    codes: Iterable[str] = _SCHEMA_WARNING_CODES,
    max_examples: int = _MAX_WARNING_EXAMPLES,
) -> List[str]:
    """
    Collapse per-sample schema issues into one warning line per code:
    SCHEMA_ISSUE [CODE] count=N examples=[at most max_examples]
    """
    code_set = frozenset(codes)
    buckets: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "examples": []})
    for issue in issues:
        if issue.code not in code_set:
            continue
        bucket = buckets[issue.code]
        bucket["count"] += 1
        if len(bucket["examples"]) < max_examples:
            if issue.sample_key:
                bucket["examples"].append(f"{issue.sample_key}: {issue.message}")
            else:
                bucket["examples"].append(issue.message)

    warnings: List[str] = []
    for code in sorted(buckets.keys()):
        data = buckets[code]
        examples_str = ", ".join(data["examples"])
        warnings.append(
            f"SCHEMA_ISSUE [{code}] count={data['count']} examples=[{examples_str}]"
        )
    return warnings


def _append_bounded_warning(warnings: List[str], message: str, max_total: int = _MAX_RUNTIME_WARNINGS) -> None:
    """Append a warning if under the total cap; drop further messages once full."""
    if len(warnings) < max_total:
        warnings.append(message)



class FacesetMetadataStatus(Enum):
    LOADED = "loaded"
    MISSING = "missing"
    UNSUPPORTED_SCHEMA = "unsupported_schema"
    INVALID_FILE = "invalid_file"
    FINGERPRINT_MISMATCH = "fingerprint_mismatch"
    PARTIAL_MATCH = "partial_match"
    SAMPLE_KEY_COLLISION = "sample_key_collision"



def _empty_bool(n: int = 0) -> np.ndarray:
    return np.empty(0, dtype=np.bool_) if n == 0 else np.zeros(n, dtype=np.bool_)


@dataclass
class RuntimeMetadata:
    status: FacesetMetadataStatus
    sample_count: int
    matched_count: int
    matched_ratio: float
    quality_scores: np.ndarray        # float32[N], default 1.0
    yaw_bucket_ids: np.ndarray        # int16[N], default UNKNOWN_BUCKET_ID (-1)
    pitch_bucket_ids: np.ndarray      # int16[N], default UNKNOWN_BUCKET_ID (-1)
    pose_valid: np.ndarray            # bool[N], default False
    quality_valid: np.ndarray         # bool[N], default False
    metadata_valid: np.ndarray        # bool[N], default False
    dataset_fingerprint: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    fallback_reason: Optional[str] = None
    # Per-sample validity contract arrays (Ticket 14 §4). Defaults keep older call sites working.
    record_matched: np.ndarray = field(default_factory=_empty_bool)
    image_valid: np.ndarray = field(default_factory=_empty_bool)
    landmarks_valid: np.ndarray = field(default_factory=_empty_bool)
    # Ticket 17 trusted-match stats. matched_count == trusted_matched_count.
    id_matched_count: int = 0
    signature_matched_count: int = 0
    stale_signature_count: int = 0
    missing_record_count: int = 0
    duplicate_count: int = 0
    trusted_matched_count: int = 0
    signature_mode: str = SIGNATURE_MODE_QUICK

    def is_usable_for_sampling(self, min_ratio: float = 0.90) -> bool:
        """
        Determine if runtime metadata status is reliable enough for custom sampling.
        """
        if self.status == FacesetMetadataStatus.LOADED:
            return True
        if self.status == FacesetMetadataStatus.PARTIAL_MATCH and self.matched_ratio >= min_ratio:
            return True
        return False

    def usable_for_pose_sampling(self) -> np.ndarray:
        """Per-sample: metadata structure OK and pose business-valid."""
        n = self.sample_count
        if len(self.pose_valid) != n or len(self.metadata_valid) != n:
            return _empty_bool(n) if n else _empty_bool()
        return self.metadata_valid & self.pose_valid

    def usable_for_quality_sampling(self) -> np.ndarray:
        """Per-sample: metadata structure OK and quality business-valid."""
        n = self.sample_count
        if len(self.quality_valid) != n or len(self.metadata_valid) != n:
            return _empty_bool(n) if n else _empty_bool()
        return self.metadata_valid & self.quality_valid


class FacesetMetadataLoader:
    """
    Safely load metadata sidecar and map runtime Sample objects to compact NumPy arrays.
    """

    @classmethod
    def load(
        cls,
        samples_path: Path,
        samples: List[Any],
        metadata_path: Optional[Path] = None,
        min_match_ratio: float = 0.90,
        strict: bool = False,
    ) -> RuntimeMetadata:
        samples_path = Path(samples_path).resolve()
        N = len(samples)

        if N == 0:
            return RuntimeMetadata(
                status=FacesetMetadataStatus.MISSING,
                sample_count=0,
                matched_count=0,
                matched_ratio=0.0,
                quality_scores=np.empty(0, dtype=np.float32),
                yaw_bucket_ids=np.empty(0, dtype=np.int16),
                pitch_bucket_ids=np.empty(0, dtype=np.int16),
                pose_valid=np.empty(0, dtype=np.bool_),
                quality_valid=np.empty(0, dtype=np.bool_),
                metadata_valid=np.empty(0, dtype=np.bool_),
                fallback_reason="NO_SAMPLES_PROVIDED",
                record_matched=np.empty(0, dtype=np.bool_),
                image_valid=np.empty(0, dtype=np.bool_),
                landmarks_valid=np.empty(0, dtype=np.bool_),
            )

        if metadata_path is None:
            target_meta_path = samples_path / "faceset_metadata.v1.json"
        else:
            target_meta_path = Path(metadata_path).resolve()

        # Initialize neutral compact arrays
        quality_scores = np.ones(N, dtype=np.float32)
        yaw_bucket_ids = np.full(N, UNKNOWN_BUCKET_ID, dtype=np.int16)
        pitch_bucket_ids = np.full(N, UNKNOWN_BUCKET_ID, dtype=np.int16)
        pose_valid = np.zeros(N, dtype=np.bool_)
        quality_valid = np.zeros(N, dtype=np.bool_)
        metadata_valid = np.zeros(N, dtype=np.bool_)
        record_matched = np.zeros(N, dtype=np.bool_)
        image_valid = np.zeros(N, dtype=np.bool_)
        landmarks_valid = np.zeros(N, dtype=np.bool_)

        def _neutral_runtime(
            status,
            fallback_reason,
            matched_count=0,
            matched_ratio=0.0,
            warnings=None,
            dataset_fingerprint=None,
            id_matched_count=0,
            signature_matched_count=0,
            stale_signature_count=0,
            missing_record_count=0,
            duplicate_count=0,
            signature_mode=SIGNATURE_MODE_QUICK,
        ):
            return RuntimeMetadata(
                status=status,
                sample_count=N,
                matched_count=matched_count,
                matched_ratio=matched_ratio,
                quality_scores=quality_scores,
                yaw_bucket_ids=yaw_bucket_ids,
                pitch_bucket_ids=pitch_bucket_ids,
                pose_valid=pose_valid,
                quality_valid=quality_valid,
                metadata_valid=metadata_valid,
                dataset_fingerprint=dataset_fingerprint,
                warnings=list(warnings or []),
                fallback_reason=fallback_reason,
                record_matched=record_matched,
                image_valid=image_valid,
                landmarks_valid=landmarks_valid,
                id_matched_count=id_matched_count,
                signature_matched_count=signature_matched_count,
                stale_signature_count=stale_signature_count,
                missing_record_count=missing_record_count,
                duplicate_count=duplicate_count,
                trusted_matched_count=matched_count,
                signature_mode=signature_mode,
            )

        # 1. Attempt to load metadata JSON
        if not target_meta_path.exists():
            return _neutral_runtime(
                FacesetMetadataStatus.MISSING,
                "METADATA_FILE_NOT_FOUND",
            )

        loaded_meta, val_res = load_metadata(target_meta_path)

        # Check for JSON parse / structural errors first
        if any(i.code in ("JSON_PARSE_ERROR", "INVALID_TOP_LEVEL") for i in val_res.issues):
            return _neutral_runtime(
                FacesetMetadataStatus.INVALID_FILE,
                "INVALID_METADATA_FILE_JSON",
            )

        # Check for unsupported schema version
        if not val_res.is_supported or any(i.code == "UNSUPPORTED_SCHEMA_VERSION" for i in val_res.issues):
            return _neutral_runtime(
                FacesetMetadataStatus.UNSUPPORTED_SCHEMA,
                f"UNSUPPORTED_SCHEMA_VERSION_{loaded_meta.schema_version}",
            )

        # 2. Index saved metadata records by sample_id
        meta_by_id: Dict[str, dict] = {}
        duplicate_ids = set()

        for s_rec in loaded_meta.samples:
            if isinstance(s_rec, dict):
                sid = s_rec.get("sample_id")
                if sid:
                    if sid in meta_by_id:
                        duplicate_ids.add(sid)
                    else:
                        meta_by_id[sid] = s_rec

        warnings: List[str] = []
        if val_res and val_res.issues:
            for schema_warn in _aggregate_schema_issues_to_warnings(val_res.issues):
                _append_bounded_warning(warnings, schema_warn)

        if len(duplicate_ids) > 0:
            _append_bounded_warning(
                warnings,
                f"Detected {len(duplicate_ids)} duplicate sample_id records in metadata.",
            )

        alias_yaw_count = 0
        alias_yaw_examples: List[str] = []
        alias_pitch_count = 0
        alias_pitch_examples: List[str] = []
        unknown_yaw_count = 0
        unknown_yaw_examples: List[str] = []
        unknown_pitch_count = 0
        unknown_pitch_examples: List[str] = []
        duplicate_collision_count = 0

        # 3. Trusted match: sample_id match AND signature match under saved mode.
        is_packed = any(getattr(s, "_filename_offset_size", None) is not None for s in samples)
        signature_mode = signature_mode_from_analysis_config(
            getattr(loaded_meta, "analysis_config", None)
        )
        id_matched_count = 0
        signature_matched_count = 0
        stale_signature_count = 0
        missing_record_count = 0
        trusted_matched_count = 0
        current_sig_objects = []

        for i, s in enumerate(samples):
            person_name = getattr(s, "person_name", None)
            raw_filename = getattr(s, "filename", str(i))
            key = build_sample_key(raw_filename, person_name=person_name, is_packed=is_packed, faceset_root=samples_path)
            sid = build_sample_id(key)

            # Build current signature under the saved metadata mode so strong
            # sidecars are compared with strong current hashes.
            sig = build_signature_from_sample(
                sample=s,
                sample_key=key,
                samples_path=samples_path,
                mode=signature_mode,
            )
            current_sig_objects.append(sig)

            # Match against indexed records
            if sid in duplicate_ids:
                duplicate_collision_count += 1
                continue

            if sid not in meta_by_id:
                missing_record_count += 1
                continue

            rec = meta_by_id[sid]
            id_matched_count += 1
            # Ticket 14 contract: record_matched means unique sample_id hit.
            record_matched[i] = True

            saved_sig = rec.get("signature") if isinstance(rec, dict) else None
            if saved_sig is None:
                # Legacy sidecar without per-sample signature: keep diagnostic mapping,
                # but do not claim a cryptographic signature match.
                sig_ok = True
                legacy_unsigned = True
            else:
                legacy_unsigned = False
                sig_ok = signatures_match(saved_sig, sig, mode=signature_mode)

            if not sig_ok:
                # Same-name / same-id replacement: never trust old quality/pose.
                stale_signature_count += 1
                continue

            if not legacy_unsigned:
                signature_matched_count += 1
            # Trusted for sampling when id matches and signature is OK (or legacy unsigned).
            trusted_matched_count += 1

            # Independent child flags first (R5-01): a malformed sibling must not
            # prevent safe accessors from filling other diagnostic arrays.
            # Sampling safety remains metadata_valid & business_valid.
            image_valid[i] = get_record_image_valid(rec)
            landmarks_valid[i] = get_record_landmarks_valid(rec)

            # Quality validity and extraction
            if get_record_quality_valid(rec):
                try:
                    q_score = float(rec["quality"]["quality_score"])
                    quality_scores[i] = q_score
                    quality_valid[i] = True
                except (ValueError, TypeError, KeyError):
                    pass

            # Pose validity and extraction using contract accessors
            norm_yaw, y_id, y_valid = get_record_yaw_bucket(rec)
            norm_pitch, p_id, p_valid = get_record_pitch_bucket(rec)

            p_info = rec.get("pose", {})
            if isinstance(p_info, dict):
                raw_y_str = p_info.get("yaw_bucket")
                if isinstance(raw_y_str, str):
                    raw_y_clean = raw_y_str.strip()
                    if raw_y_clean in LEGACY_YAW_ALIASES:
                        alias_yaw_count += 1
                        if len(alias_yaw_examples) < _MAX_WARNING_EXAMPLES:
                            alias_yaw_examples.append(f"{key}: '{raw_y_clean}' -> '{norm_yaw}'")
                    elif not y_valid and raw_y_clean != "unknown":
                        unknown_yaw_count += 1
                        if len(unknown_yaw_examples) < _MAX_WARNING_EXAMPLES:
                            unknown_yaw_examples.append(f"{key}: '{raw_y_clean}'")

                raw_p_str = p_info.get("pitch_bucket")
                if isinstance(raw_p_str, str):
                    raw_p_clean = raw_p_str.strip()
                    if raw_p_clean in LEGACY_PITCH_ALIASES:
                        alias_pitch_count += 1
                        if len(alias_pitch_examples) < _MAX_WARNING_EXAMPLES:
                            alias_pitch_examples.append(f"{key}: '{raw_p_clean}' -> '{norm_pitch}'")
                    elif not p_valid and raw_p_clean != "unknown":
                        unknown_pitch_count += 1
                        if len(unknown_pitch_examples) < _MAX_WARNING_EXAMPLES:
                            unknown_pitch_examples.append(f"{key}: '{raw_p_clean}'")

            is_pose_record_valid = get_record_pose_valid(rec)
            if y_valid and is_pose_record_valid:
                yaw_bucket_ids[i] = y_id
                pose_valid[i] = True
            elif y_valid and not is_pose_record_valid:
                yaw_bucket_ids[i] = y_id
                pose_valid[i] = False

            if p_valid:
                pitch_bucket_ids[i] = p_id

            # Structural gate is independent of per-child business validity.
            metadata_valid[i] = is_record_structurally_valid(rec)

        # Collect bounded match-time warnings (one line per issue family).
        if duplicate_collision_count > 0:
            _append_bounded_warning(
                warnings,
                f"DUPLICATE_SAMPLE_ID_COLLISION count={duplicate_collision_count}",
            )
        if stale_signature_count > 0:
            _append_bounded_warning(
                warnings,
                f"STALE_SIGNATURE_TOTAL count={stale_signature_count}",
            )
        if missing_record_count > 0:
            _append_bounded_warning(
                warnings,
                f"MISSING_METADATA_RECORD count={missing_record_count}",
            )
        if alias_yaw_count > 0:
            _append_bounded_warning(
                warnings,
                f"LEGACY_YAW_ALIAS_USED count={alias_yaw_count} examples=[{', '.join(alias_yaw_examples)}]",
            )
        if alias_pitch_count > 0:
            _append_bounded_warning(
                warnings,
                f"LEGACY_PITCH_ALIAS_USED count={alias_pitch_count} examples=[{', '.join(alias_pitch_examples)}]",
            )
        if unknown_yaw_count > 0:
            _append_bounded_warning(
                warnings,
                f"UNKNOWN_YAW_BUCKET count={unknown_yaw_count} examples=[{', '.join(unknown_yaw_examples)}]",
            )
        if unknown_pitch_count > 0:
            _append_bounded_warning(
                warnings,
                f"UNKNOWN_PITCH_BUCKET count={unknown_pitch_count} examples=[{', '.join(unknown_pitch_examples)}]",
            )

        # matched_count semantics: trusted matches only (id + signature).
        matched_count = trusted_matched_count
        matched_ratio = matched_count / float(N)
        current_fingerprint = build_dataset_fingerprint(current_sig_objects)
        saved_fingerprint = loaded_meta.dataset.get("fingerprint")

        # 4. Status Determination
        if saved_fingerprint == current_fingerprint and matched_ratio == 1.0:
            status = FacesetMetadataStatus.LOADED
            fallback_reason = None
        elif matched_ratio >= min_match_ratio:
            status = FacesetMetadataStatus.PARTIAL_MATCH
            _append_bounded_warning(
                warnings,
                f"Fingerprint mismatch or partial trusted match: {matched_count}/{N} trusted ({matched_ratio * 100.0:.1f}%).",
            )
            fallback_reason = None
        else:
            status = FacesetMetadataStatus.FINGERPRINT_MISMATCH
            fallback_reason = f"MATCH_RATIO_TOO_LOW_{matched_ratio:.2f}_BELOW_{min_match_ratio:.2f}"
            _append_bounded_warning(
                warnings,
                f"Trusted match ratio {matched_ratio:.2f} below threshold {min_match_ratio:.2f}.",
            )

        if strict and status != FacesetMetadataStatus.LOADED:
            _append_bounded_warning(
                warnings,
                "Strict mode enabled and metadata is not perfectly LOADED.",
            )

        return RuntimeMetadata(
            status=status,
            sample_count=N,
            matched_count=matched_count,
            matched_ratio=matched_ratio,
            quality_scores=quality_scores,
            yaw_bucket_ids=yaw_bucket_ids,
            pitch_bucket_ids=pitch_bucket_ids,
            pose_valid=pose_valid,
            quality_valid=quality_valid,
            metadata_valid=metadata_valid,
            dataset_fingerprint=saved_fingerprint,
            warnings=warnings,
            fallback_reason=fallback_reason,
            record_matched=record_matched,
            image_valid=image_valid,
            landmarks_valid=landmarks_valid,
            id_matched_count=id_matched_count,
            signature_matched_count=signature_matched_count,
            stale_signature_count=stale_signature_count,
            missing_record_count=missing_record_count,
            duplicate_count=duplicate_collision_count,
            trusted_matched_count=trusted_matched_count,
            signature_mode=signature_mode,
        )
