from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from samplelib.metadata.contracts import (
    LEGACY_PITCH_ALIASES,
    LEGACY_YAW_ALIASES,
    PITCH_BUCKET_NAME_TO_ID,
    UNKNOWN_BUCKET_ID,
    YAW_BUCKET_NAME_TO_ID,
    get_pitch_bucket_id,
    get_record_image_valid,
    get_record_pitch_bucket,
    get_record_pose_valid,
    get_record_quality_valid,
    get_record_yaw_bucket,
    get_yaw_bucket_id,
)
from samplelib.metadata.fingerprint import build_dataset_fingerprint, build_sample_signature
from samplelib.metadata.identity import build_sample_id, build_sample_key
from samplelib.metadata.schema import SCHEMA_VERSION_CURRENT, FacesetMetadataV1
from samplelib.metadata.store import load_metadata



class FacesetMetadataStatus(Enum):
    LOADED = "loaded"
    MISSING = "missing"
    UNSUPPORTED_SCHEMA = "unsupported_schema"
    INVALID_FILE = "invalid_file"
    FINGERPRINT_MISMATCH = "fingerprint_mismatch"
    PARTIAL_MATCH = "partial_match"
    SAMPLE_KEY_COLLISION = "sample_key_collision"



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

    def is_usable_for_sampling(self, min_ratio: float = 0.90) -> bool:
        """
        Determine if runtime metadata status is reliable enough for custom sampling.
        """
        if self.status == FacesetMetadataStatus.LOADED:
            return True
        if self.status == FacesetMetadataStatus.PARTIAL_MATCH and self.matched_ratio >= min_ratio:
            return True
        return False


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

        # 1. Attempt to load metadata JSON
        if not target_meta_path.exists():
            return RuntimeMetadata(
                status=FacesetMetadataStatus.MISSING,
                sample_count=N,
                matched_count=0,
                matched_ratio=0.0,
                quality_scores=quality_scores,
                yaw_bucket_ids=yaw_bucket_ids,
                pitch_bucket_ids=pitch_bucket_ids,
                pose_valid=pose_valid,
                quality_valid=quality_valid,
                metadata_valid=metadata_valid,
                fallback_reason="METADATA_FILE_NOT_FOUND",
            )

        loaded_meta, val_res = load_metadata(target_meta_path)

        # Check for JSON parse / structural errors first
        if any(i.code in ("JSON_PARSE_ERROR", "INVALID_TOP_LEVEL") for i in val_res.issues):
            return RuntimeMetadata(
                status=FacesetMetadataStatus.INVALID_FILE,
                sample_count=N,
                matched_count=0,
                matched_ratio=0.0,
                quality_scores=quality_scores,
                yaw_bucket_ids=yaw_bucket_ids,
                pitch_bucket_ids=pitch_bucket_ids,
                pose_valid=pose_valid,
                quality_valid=quality_valid,
                metadata_valid=metadata_valid,
                fallback_reason="INVALID_METADATA_FILE_JSON",
            )

        # Check for unsupported schema version
        if not val_res.is_supported or any(i.code == "UNSUPPORTED_SCHEMA_VERSION" for i in val_res.issues):
            return RuntimeMetadata(
                status=FacesetMetadataStatus.UNSUPPORTED_SCHEMA,
                sample_count=N,
                matched_count=0,
                matched_ratio=0.0,
                quality_scores=quality_scores,
                yaw_bucket_ids=yaw_bucket_ids,
                pitch_bucket_ids=pitch_bucket_ids,
                pose_valid=pose_valid,
                quality_valid=quality_valid,
                metadata_valid=metadata_valid,
                fallback_reason=f"UNSUPPORTED_SCHEMA_VERSION_{loaded_meta.schema_version}",
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

        warnings = []
        if val_res and val_res.issues:
            for issue in val_res.issues:
                if issue.code in (
                    "LEGACY_YAW_BUCKET_ALIAS",
                    "LEGACY_PITCH_BUCKET_ALIAS",
                    "INVALID_POSE_MAPPING",
                    "INVALID_POSE_VALID_TYPE",
                    "INVALID_YAW_BUCKET",
                    "INVALID_PITCH_BUCKET",
                ):
                    warnings.append(f"SCHEMA_ISSUE [{issue.code}] {issue.message}")

        if len(duplicate_ids) > 0:
            warnings.append(f"Detected {len(duplicate_ids)} duplicate sample_id records in metadata.")


        alias_yaw_count = 0
        alias_yaw_examples = []
        alias_pitch_count = 0
        alias_pitch_examples = []
        unknown_yaw_count = 0
        unknown_yaw_examples = []
        unknown_pitch_count = 0
        unknown_pitch_examples = []

        # 3. Identity mapping against runtime samples
        is_packed = any(getattr(s, "_filename_offset_size", None) is not None for s in samples)
        matched_count = 0
        current_sig_objects = []

        for i, s in enumerate(samples):
            person_name = getattr(s, "person_name", None)
            raw_filename = getattr(s, "filename", str(i))
            key = build_sample_key(raw_filename, person_name=person_name, is_packed=is_packed, faceset_root=samples_path)
            sid = build_sample_id(key)

            # Signature collection for dataset fingerprint check
            off_size = getattr(s, "_filename_offset_size", None)
            if off_size is not None:
                _, offset, size = off_size
                sig = build_sample_signature(key, byte_size=size, packed_offset=offset)
            else:
                abs_fp = samples_path / key if not Path(key).is_absolute() else Path(key)
                if abs_fp.exists():
                    stat = abs_fp.stat()
                    sig = build_sample_signature(key, byte_size=stat.st_size, mtime_ns=stat.st_mtime_ns)
                else:
                    sig = build_sample_signature(key, byte_size=0)
            current_sig_objects.append(sig)

            # Match against indexed records
            if sid in duplicate_ids:
                warnings.append(f"Sample {key} collision in duplicate IDs, retaining neutral default.")
                continue

            if sid in meta_by_id:
                rec = meta_by_id[sid]
                matched_count += 1

                # Check record structural validity (must have valid child dict)
                has_child_container = (
                    isinstance(rec.get("pose"), dict)
                    or isinstance(rec.get("quality"), dict)
                    or isinstance(rec.get("image"), dict)
                )
                if not isinstance(rec, dict) or not has_child_container:
                    metadata_valid[i] = False
                    continue

                metadata_valid[i] = True


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
                            if len(alias_yaw_examples) < 5:
                                alias_yaw_examples.append(f"{key}: '{raw_y_clean}' -> '{norm_yaw}'")
                        elif not y_valid and raw_y_clean != "unknown":
                            unknown_yaw_count += 1
                            if len(unknown_yaw_examples) < 5:
                                unknown_yaw_examples.append(f"{key}: '{raw_y_clean}'")

                    raw_p_str = p_info.get("pitch_bucket")
                    if isinstance(raw_p_str, str):
                        raw_p_clean = raw_p_str.strip()
                        if raw_p_clean in LEGACY_PITCH_ALIASES:
                            alias_pitch_count += 1
                            if len(alias_pitch_examples) < 5:
                                alias_pitch_examples.append(f"{key}: '{raw_p_clean}' -> '{norm_pitch}'")
                        elif not p_valid and raw_p_clean != "unknown":
                            unknown_pitch_count += 1
                            if len(unknown_pitch_examples) < 5:
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

        # Collect bounded warnings
        if alias_yaw_count > 0:
            warnings.append(
                f"LEGACY_YAW_ALIAS_USED count={alias_yaw_count} examples=[{', '.join(alias_yaw_examples)}]"
            )
        if alias_pitch_count > 0:
            warnings.append(
                f"LEGACY_PITCH_ALIAS_USED count={alias_pitch_count} examples=[{', '.join(alias_pitch_examples)}]"
            )
        if unknown_yaw_count > 0:
            warnings.append(
                f"UNKNOWN_YAW_BUCKET count={unknown_yaw_count} examples=[{', '.join(unknown_yaw_examples)}]"
            )
        if unknown_pitch_count > 0:
            warnings.append(
                f"UNKNOWN_PITCH_BUCKET count={unknown_pitch_count} examples=[{', '.join(unknown_pitch_examples)}]"
            )



        matched_ratio = matched_count / float(N)
        current_fingerprint = build_dataset_fingerprint(current_sig_objects)
        saved_fingerprint = loaded_meta.dataset.get("fingerprint")

        # 4. Status Determination
        if saved_fingerprint == current_fingerprint and matched_ratio == 1.0:
            status = FacesetMetadataStatus.LOADED
            fallback_reason = None
        elif matched_ratio >= min_match_ratio:
            status = FacesetMetadataStatus.PARTIAL_MATCH
            warnings.append(
                f"Fingerprint mismatch or partial match: {matched_count}/{N} matched ({matched_ratio * 100.0:.1f}%)."
            )
            fallback_reason = None
        else:
            status = FacesetMetadataStatus.FINGERPRINT_MISMATCH
            fallback_reason = f"MATCH_RATIO_TOO_LOW_{matched_ratio:.2f}_BELOW_{min_match_ratio:.2f}"
            warnings.append(f"Match ratio {matched_ratio:.2f} below threshold {min_match_ratio:.2f}.")

        if strict and status != FacesetMetadataStatus.LOADED:
            warnings.append("Strict mode enabled and metadata is not perfectly LOADED.")

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
        )
