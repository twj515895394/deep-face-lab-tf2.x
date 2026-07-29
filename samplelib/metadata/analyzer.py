import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from samplelib import SampleLoader, SampleType
from samplelib.metadata.fingerprint import SampleSignature, build_dataset_fingerprint, build_sample_signature
from samplelib.metadata.identity import build_sample_id, build_sample_key
from samplelib.metadata.pose import FacesetPoseConfig, analyze_pose, validate_landmarks
from samplelib.metadata.quality import FacesetQualityConfig, compute_raw_quality, finalize_quality_scores, validate_image
from samplelib.metadata.schema import FacesetMetadataV1, MetadataValidationIssue, MetadataValidationResult



@dataclass
class FacesetAnalyzerConfig:
    pose_config: FacesetPoseConfig = field(default_factory=FacesetPoseConfig)
    quality_config: FacesetQualityConfig = field(default_factory=FacesetQualityConfig)
    strict: bool = False
    analyzer_version: str = "v1.0"


@dataclass
class AnalyzerResult:
    metadata: FacesetMetadataV1
    summary: Dict
    failures: List[Dict]
    timing: Dict
    validation: MetadataValidationResult


class FacesetAnalyzer:
    """
    Lightweight Two-Pass Faceset Analyzer.
    Analyzes image validity, landmark integrity, head pose buckets,
    sharpness, and blended quality scores without extra deep learning dependencies.
    """
    def __init__(self, config: Optional[FacesetAnalyzerConfig] = None):
        self.config = config if config is not None else FacesetAnalyzerConfig()

    def analyze(self, samples_path: Path) -> AnalyzerResult:
        t_start = time.time()
        samples_path = Path(samples_path)

        if not samples_path.exists():
            raise FileNotFoundError(f"Samples path does not exist: {samples_path}")

        # Load samples (supports Ordinary folder, Person subfolders, and Packed faceset.pak)
        samples = SampleLoader.load(SampleType.FACE, samples_path)
        samples_len = len(samples)

        if samples_len == 0:
            raise ValueError(f"No training data provided at {samples_path}")

        pass1_records = []
        signatures = []
        failures = []

        is_packed = any(getattr(s, "_filename_offset_size", None) is not None for s in samples)
        has_person_name = any(getattr(s, "person_name", None) is not None for s in samples)
        dataset_format = "packed" if is_packed else ("person" if has_person_name else "ordinary")


        # ----------------------------------------------------
        # Pass 1: Per-Sample Raw Metrics Extraction
        # ----------------------------------------------------
        for idx, sample in enumerate(samples):
            person_name = getattr(sample, "person_name", None)
            raw_filename = getattr(sample, "filename", str(idx))
            sample_key = build_sample_key(raw_filename, person_name=person_name, is_packed=is_packed, faceset_root=samples_path)
            sample_id = build_sample_id(sample_key)


            sample_issues = []

            # Extract Signature metadata
            off_size = getattr(sample, "_filename_offset_size", None)
            if off_size is not None:
                _, offset, size = off_size
                sig = build_sample_signature(sample_key, byte_size=size, packed_offset=offset)
            else:
                abs_fp = samples_path / sample_key if not Path(sample_key).is_absolute() else Path(sample_key)
                if abs_fp.exists():
                    stat = abs_fp.stat()
                    sig = build_sample_signature(sample_key, byte_size=stat.st_size, mtime_ns=stat.st_mtime_ns)
                else:
                    sig = build_sample_signature(sample_key, byte_size=0)
            signatures.append(sig)

            # Load image once
            bgr_img = None
            try:
                bgr_img = sample.load_bgr()
            except Exception as e:
                sample_issues.append(f"IMAGE_LOAD_ERROR_{type(e).__name__}")

            img_val = validate_image(bgr_img)
            if not img_val.valid:
                sample_issues.extend(img_val.issues)

            raw_q = compute_raw_quality(bgr_img, self.config.quality_config) if img_val.valid else None

            img_shape = bgr_img.shape if img_val.valid else getattr(sample, "shape", None)
            pose_res = analyze_pose(getattr(sample, "landmarks", None), img_shape=img_shape, config=self.config.pose_config)
            if not pose_res.valid:
                sample_issues.extend(pose_res.issues)

            if len(sample_issues) > 0:
                failures.append({
                    "sample_key": sample_key,
                    "sample_id": sample_id,
                    "issues": sample_issues,
                })

            pass1_records.append({
                "sample_id": sample_id,
                "sample_key": sample_key,
                "signature": sig.to_dict(),
                "image": {
                    "valid": img_val.valid,
                    "height": img_val.height,
                    "width": img_val.width,
                    "channels": img_val.channels,
                },
                "landmarks": {
                    "valid": pose_res.valid,
                },
                "pose": {
                    "valid": pose_res.valid,
                    "pitch": pose_res.pitch,
                    "yaw": pose_res.yaw,
                    "roll": pose_res.roll,
                    "yaw_bucket": pose_res.yaw_bucket,
                    "pitch_bucket": pose_res.pitch_bucket,
                },
                "quality_raw": {
                    "valid": raw_q.valid if raw_q else False,
                    "sharpness_raw": raw_q.sharpness_raw if raw_q else None,
                    "dark_ratio": raw_q.dark_ratio if raw_q else None,
                    "bright_ratio": raw_q.bright_ratio if raw_q else None,
                    "exposure_score": raw_q.exposure_score if raw_q else None,
                },
                "issues": sample_issues,
            })

            # Clear pixel reference after pass 1 to keep RAM footprint low
            del bgr_img

        # ----------------------------------------------------
        # Pass 2: Faceset-Wide Percentile Normalization
        # ----------------------------------------------------
        finalized_samples, norm_summary = finalize_quality_scores(pass1_records, self.config.quality_config)
        dataset_fingerprint = build_dataset_fingerprint(signatures)

        # ----------------------------------------------------
        # Summary & Statistics Aggregation
        # ----------------------------------------------------
        yaw_counts = {}
        pitch_counts = {}
        valid_quality_scores = []

        for s in finalized_samples:
            y_b = s["pose"]["yaw_bucket"]
            p_b = s["pose"]["pitch_bucket"]
            yaw_counts[y_b] = yaw_counts.get(y_b, 0) + 1
            pitch_counts[p_b] = pitch_counts.get(p_b, 0) + 1

            q_val = s["quality"].get("quality_score")
            if q_val is not None and math.isfinite(q_val):
                valid_quality_scores.append(q_val)

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

        summary = {
            "total_samples": samples_len,
            "valid_samples": samples_len - len(failures),
            "invalid_samples": len(failures),
            "yaw_bucket_counts": yaw_counts,
            "pitch_bucket_counts": pitch_counts,
            "quality_stats": q_stats,
            "normalization": norm_summary,
        }

        timing = {
            "total_seconds": float(time.time() - t_start),
            "per_sample_ms": float((time.time() - t_start) / max(1, samples_len) * 1000.0),
        }

        dataset_meta = {
            "format": dataset_format,
            "fingerprint": dataset_fingerprint,
            "sample_count": samples_len,
        }

        metadata_inst = FacesetMetadataV1(
            schema_version=1,
            analyzer_version=self.config.analyzer_version,
            dataset=dataset_meta,
            analysis_config={
                "pose": {
                    "yaw_thresholds": list(self.config.pose_config.yaw_thresholds),
                    "pitch_thresholds": list(self.config.pose_config.pitch_thresholds),
                },
                "quality": {
                    "dark_threshold": self.config.quality_config.dark_threshold,
                    "bright_threshold": self.config.quality_config.bright_threshold,
                    "sharpness_weight": self.config.quality_config.sharpness_weight,
                    "exposure_weight": self.config.quality_config.exposure_weight,
                },
            },
            summary=summary,
            samples=finalized_samples,
        )

        validation_res = metadata_inst.validate()
        return AnalyzerResult(
            metadata=metadata_inst,
            summary=summary,
            failures=failures,
            timing=timing,
            validation=validation_res,
        )
