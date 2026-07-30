import math
import multiprocessing
import os
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from samplelib import SampleLoader, SampleType
from samplelib.metadata.fingerprint import (
    DEFAULT_QUICK_CHUNK_SIZE,
    SIGNATURE_MODE_QUICK,
    SIGNATURE_MODE_STRONG,
    SampleSignature,
    build_dataset_fingerprint,
    build_signature_from_sample,
    compute_content_sha256,
    compute_quick_hash,
    signature_config_dict,
)
from samplelib.metadata.identity import build_sample_id, build_sample_key
from samplelib.metadata.pose import FacesetPoseConfig, analyze_pose
from samplelib.metadata.quality import (
    FacesetQualityConfig,
    compute_raw_quality,
    finalize_quality_scores,
    validate_image,
)
from samplelib.metadata.schema import FacesetMetadataV1, MetadataValidationResult


def resolve_worker_count(workers: Optional[int]) -> int:
    """
    workers=None -> auto, bounded by min(cpu_count, 8)
    workers=1 -> single process
    workers=N -> up to N
    workers<=0 -> ValueError
    """
    if workers is None:
        cpu = os.cpu_count() or 1
        return max(1, min(int(cpu), 8))
    w = int(workers)
    if w <= 0:
        raise ValueError(f"workers must be >= 1 or None for auto, got {workers}")
    return w


def _bgr_from_raw_bytes(raw: bytes) -> Optional[np.ndarray]:
    if not raw:
        return None
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def _load_raw_bytes_from_task(task: dict) -> bytes:
    packed_path = task.get("packed_path")
    if packed_path:
        with open(packed_path, "rb") as f:
            f.seek(int(task["packed_offset"]))
            return f.read(int(task["packed_size"]))
    ordinary_path = task.get("ordinary_path")
    if not ordinary_path:
        raise FileNotFoundError("Task has neither packed_path nor ordinary_path")
    with open(ordinary_path, "rb") as f:
        return f.read()


def analyze_sample_task(task: dict) -> dict:
    """
    Top-level worker entry (must be module-global for Windows spawn).
    Returns a small mapping only — never BGR pixels.
    """
    sample_key = task["sample_key"]
    sample_id = task["sample_id"]
    mode = task.get("signature_mode", SIGNATURE_MODE_QUICK)
    chunk_size = int(task.get("chunk_size", DEFAULT_QUICK_CHUNK_SIZE))
    pose_raw = task["pose_config"]
    pose_cfg = FacesetPoseConfig(
        yaw_thresholds=tuple(pose_raw.get("yaw_thresholds", FacesetPoseConfig().yaw_thresholds)),
        pitch_thresholds=tuple(pose_raw.get("pitch_thresholds", FacesetPoseConfig().pitch_thresholds)),
    )
    quality_cfg = FacesetQualityConfig(**task["quality_config"])

    sample_issues: List[str] = []
    raw: Optional[bytes] = None
    try:
        raw = _load_raw_bytes_from_task(task)
    except Exception as e:
        sample_issues.append(f"RAW_READ_ERROR_{type(e).__name__}")

    # Signature
    if task.get("packed_path"):
        byte_size = int(task["packed_size"])
        mtime_ns = None
        packed_offset = int(task["packed_offset"])
    else:
        packed_offset = None
        ordinary_path = task.get("ordinary_path")
        if ordinary_path and Path(ordinary_path).is_file():
            st = Path(ordinary_path).stat()
            byte_size = int(st.st_size)
            mtime_ns = int(st.st_mtime_ns)
        else:
            byte_size = len(raw) if raw is not None else 0
            mtime_ns = None

    quick_hash = None
    content_sha256 = None
    if raw is not None:
        if byte_size <= 0:
            byte_size = len(raw)
        quick_hash = compute_quick_hash(raw, chunk_size=chunk_size)
        if mode == SIGNATURE_MODE_STRONG:
            content_sha256 = compute_content_sha256(raw)

    sig = SampleSignature(
        sample_key=sample_key,
        byte_size=byte_size,
        mtime_ns=mtime_ns,
        packed_offset=packed_offset,
        quick_hash=quick_hash,
        content_sha256=content_sha256,
    )

    bgr_img = None
    if raw is not None:
        try:
            bgr_img = _bgr_from_raw_bytes(raw)
            if bgr_img is None:
                sample_issues.append("IMAGE_DECODE_FAILED")
        except Exception as e:
            sample_issues.append(f"IMAGE_DECODE_ERROR_{type(e).__name__}")
    else:
        sample_issues.append("IMAGE_LOAD_ERROR_NO_RAW_BYTES")

    img_val = validate_image(bgr_img)
    if not img_val.valid:
        sample_issues.extend(img_val.issues)

    raw_q = compute_raw_quality(bgr_img, quality_cfg) if img_val.valid else None

    landmarks = task.get("landmarks")
    landmarks_arr = None
    if landmarks is not None:
        landmarks_arr = np.asarray(landmarks, dtype=np.float32)

    img_shape = bgr_img.shape if img_val.valid and bgr_img is not None else task.get("shape")
    pose_res = analyze_pose(landmarks_arr, img_shape=img_shape, config=pose_cfg)
    if not pose_res.valid:
        sample_issues.extend(pose_res.issues)

    # Drop large buffers before return
    del bgr_img
    del raw

    return {
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
    }


def _pose_config_to_dict(cfg: FacesetPoseConfig) -> dict:
    return {
        "yaw_thresholds": list(cfg.yaw_thresholds),
        "pitch_thresholds": list(cfg.pitch_thresholds),
    }


def _quality_config_to_dict(cfg: FacesetQualityConfig) -> dict:
    return {
        "dark_threshold": cfg.dark_threshold,
        "bright_threshold": cfg.bright_threshold,
        "sharpness_weight": cfg.sharpness_weight,
        "exposure_weight": cfg.exposure_weight,
    }


@dataclass
class FacesetAnalyzerConfig:
    pose_config: FacesetPoseConfig = field(default_factory=FacesetPoseConfig)
    quality_config: FacesetQualityConfig = field(default_factory=FacesetQualityConfig)
    strict: bool = False
    analyzer_version: str = "v1.0"
    workers: Optional[int] = None
    strong_fingerprint: bool = False
    signature_chunk_size: int = DEFAULT_QUICK_CHUNK_SIZE


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
    Supports optional multi-process workers and quick/strong signatures.
    """

    def __init__(self, config: Optional[FacesetAnalyzerConfig] = None):
        self.config = config if config is not None else FacesetAnalyzerConfig()

    @property
    def signature_mode(self) -> str:
        return (
            SIGNATURE_MODE_STRONG
            if self.config.strong_fingerprint
            else SIGNATURE_MODE_QUICK
        )

    def _build_task(self, sample: Any, samples_path: Path, is_packed: bool) -> dict:
        person_name = getattr(sample, "person_name", None)
        raw_filename = getattr(sample, "filename", "")
        sample_key = build_sample_key(
            raw_filename,
            person_name=person_name,
            is_packed=is_packed,
            faceset_root=samples_path,
        )
        sample_id = build_sample_id(sample_key)

        landmarks = getattr(sample, "landmarks", None)
        landmarks_list = None
        if landmarks is not None:
            landmarks_list = np.asarray(landmarks, dtype=np.float32).tolist()

        task: Dict[str, Any] = {
            "sample_key": sample_key,
            "sample_id": sample_id,
            "person_name": person_name,
            "landmarks": landmarks_list,
            "shape": getattr(sample, "shape", None),
            "signature_mode": self.signature_mode,
            "chunk_size": int(self.config.signature_chunk_size),
            "pose_config": _pose_config_to_dict(self.config.pose_config),
            "quality_config": _quality_config_to_dict(self.config.quality_config),
            "ordinary_path": None,
            "packed_path": None,
            "packed_offset": None,
            "packed_size": None,
        }

        off_size = getattr(sample, "_filename_offset_size", None)
        if off_size is not None:
            packed_path, offset, size = off_size
            task["packed_path"] = str(packed_path)
            task["packed_offset"] = int(offset)
            task["packed_size"] = int(size)
        else:
            path = Path(raw_filename)
            if not path.is_file():
                cand = samples_path / raw_filename
                if cand.is_file():
                    path = cand
            task["ordinary_path"] = str(path)

        return task

    def _run_pass1(self, tasks: List[dict], worker_count: int) -> List[dict]:
        if worker_count == 1 or len(tasks) <= 1:
            return [analyze_sample_task(t) for t in tasks]

        # Windows-safe spawn pool. Worker crashes propagate as core errors.
        ctx = multiprocessing.get_context("spawn")
        with ctx.Pool(processes=worker_count) as pool:
            try:
                return pool.map(analyze_sample_task, tasks)
            except Exception as e:
                # Ensure pool is closed; re-raise as core analyzer failure.
                raise RuntimeError(
                    f"Analyzer worker pool failed: {type(e).__name__}: {e}\n{traceback.format_exc()}"
                ) from e

    def analyze_samples(
        self,
        samples: List[Any],
        samples_path: Path,
    ) -> AnalyzerResult:
        """Analyze an already-loaded sample list (used by CLI incremental path)."""
        t_start = time.time()
        samples_path = Path(samples_path)
        samples_len = len(samples)
        if samples_len == 0:
            raise ValueError(f"No training data provided at {samples_path}")

        worker_count = resolve_worker_count(self.config.workers)
        is_packed = any(getattr(s, "_filename_offset_size", None) is not None for s in samples)
        has_person_name = any(getattr(s, "person_name", None) is not None for s in samples)
        dataset_format = "packed" if is_packed else ("person" if has_person_name else "ordinary")

        tasks = [self._build_task(s, samples_path, is_packed) for s in samples]
        pass1_records = self._run_pass1(tasks, worker_count)

        # Deterministic order
        pass1_records.sort(key=lambda r: str(r.get("sample_id", r.get("sample_key", ""))))

        failures = []
        signatures: List[SampleSignature] = []
        for rec in pass1_records:
            issues = rec.get("issues") or []
            if issues:
                failures.append({
                    "sample_key": rec.get("sample_key"),
                    "sample_id": rec.get("sample_id"),
                    "issues": issues,
                })
            signatures.append(SampleSignature.from_dict(rec["signature"]))

        return self._finalize_result(
            pass1_records=pass1_records,
            signatures=signatures,
            failures=failures,
            samples_len=samples_len,
            dataset_format=dataset_format,
            worker_count=worker_count,
            t_start=t_start,
        )

    def analyze(self, samples_path: Path) -> AnalyzerResult:
        t_start = time.time()
        samples_path = Path(samples_path)

        if not samples_path.exists():
            raise FileNotFoundError(f"Samples path does not exist: {samples_path}")

        samples = SampleLoader.load(SampleType.FACE, samples_path)
        return self.analyze_samples(samples, samples_path)

    def analyze_sample_keys(
        self,
        samples_by_key: Dict[str, Any],
        sample_keys: List[str],
        samples_path: Path,
        is_packed: bool,
    ) -> List[dict]:
        """Analyze a subset of samples by key (incremental recompute path)."""
        samples_path = Path(samples_path)
        worker_count = resolve_worker_count(self.config.workers)
        tasks = []
        for key in sample_keys:
            sample = samples_by_key[key]
            tasks.append(self._build_task(sample, samples_path, is_packed))
        records = self._run_pass1(tasks, worker_count)
        records.sort(key=lambda r: str(r.get("sample_id", r.get("sample_key", ""))))
        return records

    def _finalize_result(
        self,
        pass1_records: List[dict],
        signatures: List[SampleSignature],
        failures: List[Dict],
        samples_len: int,
        dataset_format: str,
        worker_count: int,
        t_start: float,
    ) -> AnalyzerResult:
        finalized_samples, norm_summary = finalize_quality_scores(
            pass1_records, self.config.quality_config
        )
        dataset_fingerprint = build_dataset_fingerprint(signatures)

        from samplelib.metadata.contracts import PITCH_BUCKET_NAMES, YAW_BUCKET_NAMES

        yaw_counts = {b: 0 for b in YAW_BUCKET_NAMES}
        yaw_counts["unknown"] = 0
        pitch_counts = {b: 0 for b in PITCH_BUCKET_NAMES}
        pitch_counts["unknown"] = 0
        valid_quality_scores = []

        for s in finalized_samples:
            y_b = s["pose"].get("yaw_bucket", "unknown")
            p_b = s["pose"].get("pitch_bucket", "unknown")
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

        # Keep top-level summary keys stable (Ticket 14 contract).
        # workers / signature mode live in analysis_config + timing.
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
            "workers_used": worker_count,
            "signature_mode": self.signature_mode,
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
                    "bucket_contract_version": 1,
                    "canonical_yaw_buckets": list(YAW_BUCKET_NAMES),
                    "canonical_pitch_buckets": list(PITCH_BUCKET_NAMES),
                    "yaw_thresholds": list(self.config.pose_config.yaw_thresholds),
                    "pitch_thresholds": list(self.config.pose_config.pitch_thresholds),
                },
                "quality": {
                    "dark_threshold": self.config.quality_config.dark_threshold,
                    "bright_threshold": self.config.quality_config.bright_threshold,
                    "sharpness_weight": self.config.quality_config.sharpness_weight,
                    "exposure_weight": self.config.quality_config.exposure_weight,
                },
                "signature": signature_config_dict(
                    self.signature_mode,
                    chunk_size=self.config.signature_chunk_size,
                ),
                "workers": {
                    "requested": self.config.workers,
                    "used": worker_count,
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
