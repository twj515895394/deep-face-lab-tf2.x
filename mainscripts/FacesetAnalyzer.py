import os
import sys
import time
from pathlib import Path
from typing import Dict, Optional

from core.interact import interact as io
from samplelib import SampleLoader, SampleType
from samplelib.metadata.analyzer import AnalyzerResult, FacesetAnalyzer, FacesetAnalyzerConfig, resolve_worker_count
from samplelib.metadata.fingerprint import (
    SIGNATURE_MODE_QUICK,
    SIGNATURE_MODE_STRONG,
    build_dataset_fingerprint,
    build_signature_from_sample,
    signature_config_dict,
    signature_mode_from_analysis_config,
)
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

    try:
        worker_count = resolve_worker_count(workers)
    except ValueError as e:
        io.log_err(f"[FacesetAnalyzer] Invalid --workers: {e}")
        return 2

    signature_mode = SIGNATURE_MODE_STRONG if strong_fingerprint else SIGNATURE_MODE_QUICK

    io.log_info(f"[FacesetAnalyzer] Starting faceset analysis for: {input_dir}")
    io.log_info(f"[FacesetAnalyzer] Target metadata file : {output_file}")
    io.log_info(f"[FacesetAnalyzer] Target report file   : {report_file}")
    io.log_info(
        f"[FacesetAnalyzer] workers requested={workers} used={worker_count} "
        f"signature_mode={signature_mode}"
    )

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

    # Build sample_key map without reading image bytes (keys only).
    sample_key_map = {}
    for idx, s in enumerate(samples):
        person_name = getattr(s, "person_name", None)
        raw_filename = getattr(s, "filename", str(idx))
        key = build_sample_key(raw_filename, person_name=person_name, is_packed=is_packed, faceset_root=input_dir)
        sample_key_map[key] = s

    # Attempt loading old metadata if incremental is requested
    old_metadata: Optional[FacesetMetadataV1] = None
    if incremental and not force and output_file.exists():
        loaded, val_res = load_metadata(output_file)
        if val_res.is_supported and val_res.is_valid:
            old_metadata = loaded
            old_mode = signature_mode_from_analysis_config(getattr(old_metadata, "analysis_config", None))
            io.log_info(
                f"[FacesetAnalyzer] Loaded existing metadata from {output_file} "
                f"for incremental processing (old_signature_mode={old_mode})."
            )
        else:
            io.log_info(f"[FacesetAnalyzer] Existing metadata invalid or unsupported, fallback to full analysis.")

    analyzer_config = FacesetAnalyzerConfig(
        strict=strict,
        workers=workers,
        strong_fingerprint=strong_fingerprint,
    )
    analyzer = FacesetAnalyzer(config=analyzer_config)

    # Signature scan only when incremental reuse is possible. Full/force runs must
    # not pre-read every sample in the main process (workers already hash once).
    current_signatures: Dict[str, dict] = {}
    need_signature_scan = bool(old_metadata is not None and incremental and not force)
    if need_signature_scan:
        for key, s in sample_key_map.items():
            sig = build_signature_from_sample(
                sample=s,
                sample_key=key,
                samples_path=input_dir,
                mode=signature_mode,
            )
            current_signatures[key] = sig.to_dict()
        plan = build_incremental_plan(
            old_metadata,
            current_signatures,
            analyzer_version=analyzer_config.analyzer_version,
            force=force,
            current_signature_mode=signature_mode,
        )
    else:
        from samplelib.metadata.incremental import IncrementalPlan

        reason = "FORCED_FULL_ANALYSIS" if force else (
            "NO_PREVIOUS_METADATA" if old_metadata is None else "FULL_ANALYSIS"
        )
        plan = IncrementalPlan(
            is_incremental=False,
            added_sample_keys=list(sample_key_map.keys()),
            reasons=[reason],
        )

    reused_count = len(plan.reused_sample_keys)
    recomputed_count = len(plan.recompute_sample_keys)
    added_count = len(plan.added_sample_keys)
    removed_count = len(plan.removed_sample_keys)

    io.log_info(
        f"[FacesetAnalyzer] Incremental plan: Reused={reused_count}, "
        f"Recomputed={recomputed_count}, Added={added_count}, Removed={removed_count}, "
        f"reasons={plan.reasons}"
    )

    try:
        if not plan.is_incremental or (recomputed_count + added_count == len(samples)):
            io.log_info(f"[FacesetAnalyzer] Running full analysis with workers={worker_count}...")
            res: AnalyzerResult = analyzer.analyze_samples(samples, input_dir)
            final_metadata = res.metadata
        else:
            target_keys = list(plan.recompute_sample_keys + plan.added_sample_keys)
            newly_analyzed_records = []
            if len(target_keys) > 0:
                io.log_info(
                    f"[FacesetAnalyzer] Analyzing {len(target_keys)} new/modified samples "
                    f"with workers={worker_count}..."
                )
                newly_analyzed_records = analyzer.analyze_sample_keys(
                    samples_by_key=sample_key_map,
                    sample_keys=target_keys,
                    samples_path=input_dir,
                    is_packed=is_packed,
                )

            final_samples, summary = reconcile_and_finalize_samples(
                plan,
                newly_analyzed_records,
                quality_config=analyzer_config.quality_config,
            )

            # Recompute fingerprint from final sample signatures
            from samplelib.metadata.fingerprint import SampleSignature

            final_sigs = []
            for rec in final_samples:
                sig_d = rec.get("signature") if isinstance(rec, dict) else None
                if isinstance(sig_d, dict):
                    final_sigs.append(SampleSignature.from_dict(sig_d))
            dataset_fingerprint = build_dataset_fingerprint(final_sigs) if final_sigs else ""

            dataset_meta = {
                "format": faceset_format,
                "fingerprint": dataset_fingerprint,
                "sample_count": len(final_samples),
            }

            from samplelib.metadata.contracts import PITCH_BUCKET_NAMES, YAW_BUCKET_NAMES

            final_metadata = FacesetMetadataV1(
                schema_version=1,
                analyzer_version=analyzer_config.analyzer_version,
                dataset=dataset_meta,
                analysis_config={
                    "pose": {
                        "bucket_contract_version": 1,
                        "canonical_yaw_buckets": list(YAW_BUCKET_NAMES),
                        "canonical_pitch_buckets": list(PITCH_BUCKET_NAMES),
                        "yaw_thresholds": list(analyzer_config.pose_config.yaw_thresholds),
                        "pitch_thresholds": list(analyzer_config.pose_config.pitch_thresholds),
                    },
                    "quality": {
                        "dark_threshold": analyzer_config.quality_config.dark_threshold,
                        "bright_threshold": analyzer_config.quality_config.bright_threshold,
                        "sharpness_weight": analyzer_config.quality_config.sharpness_weight,
                        "exposure_weight": analyzer_config.quality_config.exposure_weight,
                    },
                    "signature": signature_config_dict(signature_mode),
                    "workers": {
                        "requested": workers,
                        "used": worker_count,
                    },
                },
                summary=summary,
                samples=final_samples,
            )
    except Exception as e:
        io.log_err(f"[FacesetAnalyzer] Analysis failed: {type(e).__name__}: {e}")
        return 4

    elapsed_time = time.time() - t_start

    # Generate report before any formal Sidecar write so strict failures keep
    # the previous Metadata bytes intact.
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

    invalid_count = int((final_metadata.summary or {}).get("invalid_samples", report.invalid_samples) or 0)
    if strict and invalid_count > 0:
        io.log_err(
            f"[FacesetAnalyzer] Strict mode enabled and {invalid_count} invalid samples found; "
            f"refusing to overwrite formal Sidecar: {output_file}"
        )
        return 5

    # Atomic Write to Disk — only after analysis + strict gate succeed
    try:
        write_metadata_atomic(output_file, final_metadata, keep_backup=True)
        io.log_info(f"[FacesetAnalyzer] Successfully saved atomic metadata to: {output_file}")
    except MetadataStoreError as e:
        io.log_err(f"[FacesetAnalyzer] Atomic metadata write failed: {e}")
        return 6
    except Exception as e:
        io.log_err(f"[FacesetAnalyzer] Unexpected write error: {e}")
        return 6

    return 0
