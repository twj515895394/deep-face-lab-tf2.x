import os
import sys
import time
from pathlib import Path
from typing import Dict, Optional

from core.interact import interact as io
from samplelib import SampleLoader, SampleType
from samplelib.metadata.analyzer import AnalyzerResult, FacesetAnalyzer, FacesetAnalyzerConfig
from samplelib.metadata.fingerprint import build_dataset_fingerprint, build_sample_signature
from samplelib.metadata.identity import build_sample_id, build_sample_key
from samplelib.metadata.incremental import build_incremental_plan, reconcile_and_finalize_samples
from samplelib.metadata.report import generate_analyzer_report, print_console_summary, save_report_json
from samplelib.metadata.schema import FacesetMetadataV1
from samplelib.metadata.store import MetadataStoreError, load_metadata, write_metadata_atomic


def main(
    input_dir: Path,
    output_file: Optional[Path] = None,
    report_file: Optional[Path] = None,
    incremental: bool = False,
    force: bool = False,
    workers: Optional[int] = None,
    strong_fingerprint: bool = False,
    strict: bool = False,
) -> int:
    t_start = time.time()
    input_dir = Path(input_dir).resolve()

    if not input_dir.exists() or not input_dir.is_dir():
        io.log_err(f"[FacesetAnalyzer] Input directory does not exist or is not a directory: {input_dir}")
        return 3

    if output_file is None:
        output_file = input_dir / "faceset_metadata.v1.json"
    else:
        output_file = Path(output_file).resolve()

    if report_file is None:
        report_file = input_dir / "faceset_metadata_report.v1.json"
    else:
        report_file = Path(report_file).resolve()

    io.log_info(f"[FacesetAnalyzer] Starting faceset analysis for: {input_dir}")
    io.log_info(f"[FacesetAnalyzer] Target metadata file : {output_file}")
    io.log_info(f"[FacesetAnalyzer] Target report file   : {report_file}")

    # Check faceset format and load samples
    try:
        samples = SampleLoader.load(SampleType.FACE, input_dir)
    except Exception as e:
        io.log_err(f"[FacesetAnalyzer] Failed to load samples from {input_dir}: {e}")
        return 3

    if not samples or len(samples) == 0:
        io.log_err(f"[FacesetAnalyzer] No samples found in directory: {input_dir}")
        return 3

    is_packed = any(getattr(s, "_filename_offset_size", None) is not None for s in samples)
    has_person_name = any(getattr(s, "person_name", None) is not None for s in samples)
    faceset_format = "packed" if is_packed else ("person" if has_person_name else "ordinary")

    # Extract current signatures
    current_signatures: Dict[str, str] = {}
    current_sig_objects = []
    sample_key_map = {}

    for idx, s in enumerate(samples):
        person_name = getattr(s, "person_name", None)
        raw_filename = getattr(s, "filename", str(idx))
        key = build_sample_key(raw_filename, person_name=person_name, is_packed=is_packed, faceset_root=input_dir)

        off_size = getattr(s, "_filename_offset_size", None)
        if off_size is not None:
            _, offset, size = off_size
            sig = build_sample_signature(key, byte_size=size, packed_offset=offset)
        else:
            abs_fp = input_dir / key if not Path(key).is_absolute() else Path(key)
            if abs_fp.exists():
                stat = abs_fp.stat()
                sig = build_sample_signature(key, byte_size=stat.st_size, mtime_ns=stat.st_mtime_ns)
            else:
                sig = build_sample_signature(key, byte_size=0)

        current_signatures[key] = sig.to_dict()
        current_sig_objects.append(sig)
        sample_key_map[key] = s

    dataset_fingerprint = build_dataset_fingerprint(current_sig_objects)

    # Attempt loading old metadata if incremental is requested
    old_metadata: Optional[FacesetMetadataV1] = None
    if incremental and not force and output_file.exists():
        loaded, val_res = load_metadata(output_file)
        if val_res.is_supported and val_res.is_valid:
            old_metadata = loaded
            io.log_info(f"[FacesetAnalyzer] Loaded existing metadata from {output_file} for incremental processing.")
        else:
            io.log_info(f"[FacesetAnalyzer] Existing metadata invalid or unsupported, fallback to full analysis.")

    plan = build_incremental_plan(old_metadata, current_signatures, force=force)

    reused_count = len(plan.reused_sample_keys)
    recomputed_count = len(plan.recompute_sample_keys)
    added_count = len(plan.added_sample_keys)
    removed_count = len(plan.removed_sample_keys)

    io.log_info(
        f"[FacesetAnalyzer] Incremental plan: Reused={reused_count}, "
        f"Recomputed={recomputed_count}, Added={added_count}, Removed={removed_count}"
    )

    analyzer_config = FacesetAnalyzerConfig(strict=strict)
    analyzer = FacesetAnalyzer(config=analyzer_config)

    if not plan.is_incremental or (recomputed_count + added_count == len(samples)):
        # Run full analysis
        io.log_info("[FacesetAnalyzer] Running full analysis...")
        res: AnalyzerResult = analyzer.analyze(input_dir)
        final_metadata = res.metadata
    else:
        # Run partial analysis only on added / recomputed samples
        target_keys = set(plan.recompute_sample_keys + plan.added_sample_keys)
        newly_analyzed_records = []

        if len(target_keys) > 0:
            io.log_info(f"[FacesetAnalyzer] Analyzing {len(target_keys)} new/modified samples...")
            # For simplicity & correctness, extract raw metrics for target_keys
            for key in target_keys:
                sample = sample_key_map[key]
                sample_id = build_sample_id(key)

                # Signature
                off_size = getattr(sample, "_filename_offset_size", None)
                if off_size is not None:
                    _, offset, size = off_size
                    sig = build_sample_signature(key, byte_size=size, packed_offset=offset)
                else:
                    abs_fp = input_dir / key if not Path(key).is_absolute() else Path(key)
                    if abs_fp.exists():
                        stat = abs_fp.stat()
                        sig = build_sample_signature(key, byte_size=stat.st_size, mtime_ns=stat.st_mtime_ns)
                    else:
                        sig = build_sample_signature(key, byte_size=0)

                bgr_img = None
                issues = []
                try:
                    bgr_img = sample.load_bgr()
                except Exception as e:
                    issues.append(f"IMAGE_LOAD_ERROR_{type(e).__name__}")

                from samplelib.metadata.pose import analyze_pose
                from samplelib.metadata.quality import compute_raw_quality, validate_image

                img_val = validate_image(bgr_img)
                if not img_val.valid:
                    issues.extend(img_val.issues)

                raw_q = compute_raw_quality(bgr_img, analyzer_config.quality_config) if img_val.valid else None
                img_shape = bgr_img.shape if img_val.valid else getattr(sample, "shape", None)
                pose_res = analyze_pose(getattr(sample, "landmarks", None), img_shape=img_shape, config=analyzer_config.pose_config)
                if not pose_res.valid:
                    issues.extend(pose_res.issues)

                newly_analyzed_records.append({
                    "sample_id": sample_id,
                    "sample_key": key,
                    "signature": sig.to_dict(),
                    "image": {
                        "valid": img_val.valid,
                        "height": img_val.height,
                        "width": img_val.width,
                        "channels": img_val.channels,
                    },
                    "landmarks": {"valid": pose_res.valid},
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
                    "issues": issues,
                })
                del bgr_img

        final_samples, summary = reconcile_and_finalize_samples(plan, newly_analyzed_records)

        dataset_meta = {
            "format": faceset_format,
            "fingerprint": dataset_fingerprint,
            "sample_count": len(final_samples),
        }

        final_metadata = FacesetMetadataV1(
            schema_version=1,
            analyzer_version=analyzer_config.analyzer_version,
            dataset=dataset_meta,
            analysis_config={
                "pose": {
                    "yaw_thresholds": list(analyzer_config.pose_config.yaw_thresholds),
                    "pitch_thresholds": list(analyzer_config.pose_config.pitch_thresholds),
                },
                "quality": {
                    "dark_threshold": analyzer_config.quality_config.dark_threshold,
                    "bright_threshold": analyzer_config.quality_config.bright_threshold,
                    "sharpness_weight": analyzer_config.quality_config.sharpness_weight,
                    "exposure_weight": analyzer_config.quality_config.exposure_weight,
                },
            },
            summary=summary,
            samples=final_samples,
        )

    elapsed_time = time.time() - t_start

    # Atomic Write to Disk
    try:
        write_metadata_atomic(output_file, final_metadata, keep_backup=True)
        io.log_info(f"[FacesetAnalyzer] Successfully saved atomic metadata to: {output_file}")
    except MetadataStoreError as e:
        io.log_err(f"[FacesetAnalyzer] Atomic metadata write failed: {e}")
        return 6
    except Exception as e:
        io.log_err(f"[FacesetAnalyzer] Unexpected write error: {e}")
        return 6

    # Generate and Print Report
    report = generate_analyzer_report(
        metadata=final_metadata,
        dataset_path=input_dir,
        faceset_format=faceset_format,
        elapsed_seconds=elapsed_time,
        incremental=plan.is_incremental,
        reused_count=reused_count,
        recomputed_count=recomputed_count,
        added_count=added_count,
        removed_count=removed_count,
    )

    print_console_summary(report)

    try:
        save_report_json(report, report_file)
        io.log_info(f"[FacesetAnalyzer] Machine report saved to: {report_file}")
    except Exception as e:
        io.log_err(f"[FacesetAnalyzer] Failed to save report JSON: {e}")

    if strict and report.invalid_samples > 0:
        io.log_err(f"[FacesetAnalyzer] Strict mode enabled and {report.invalid_samples} invalid samples found!")
        return 5

    return 0
