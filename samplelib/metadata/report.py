import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.interact import interact as io
from samplelib.metadata.contracts import is_record_summary_invalid
from samplelib.metadata.schema import FacesetMetadataV1


@dataclass
class AnalyzerReport:
    created_at: str
    faceset_format: str
    dataset_path: str
    dataset_fingerprint: Optional[str]
    total_samples: int
    valid_image_samples: int
    valid_pose_samples: int
    valid_quality_samples: int
    usable_pose_samples: int
    usable_quality_samples: int
    usable_for_sampling: int  # alias of usable_pose_samples for older readers
    invalid_samples: int
    elapsed_time_seconds: float
    throughput_samples_per_sec: float
    incremental: bool
    reused_count: int
    recomputed_count: int
    added_count: int
    removed_count: int
    stale_signature_count: int = 0
    signature_upgraded_count: int = 0
    pose_distribution_yaw: Dict[str, int] = field(default_factory=dict)
    pose_distribution_pitch: Dict[str, int] = field(default_factory=dict)
    quality_stats: Dict[str, Any] = field(default_factory=dict)
    unknown_yaw_count: int = 0
    unknown_pitch_count: int = 0
    issues: List[Dict[str, Any]] = field(default_factory=list)
    invalid_samples_detail: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    disclaimer: str = (
        "Quality scores are relative heuristics for training sampling balance "
        "and do not represent final swap output resolution or photorealism."
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def generate_analyzer_report(
    metadata: FacesetMetadataV1,
    dataset_path: Path,
    faceset_format: str,
    elapsed_seconds: float,
    incremental: bool = False,
    reused_count: int = 0,
    recomputed_count: int = 0,
    added_count: int = 0,
    removed_count: int = 0,
    stale_signature_count: int = 0,
    signature_upgraded_count: int = 0,
    max_json_issues: int = 1000,
) -> AnalyzerReport:
    """
    Prefer validated Metadata.summary (single builder) for aggregate stats.
    Runtime incremental counters are attached separately.
    """
    summary = metadata.summary or {}
    dataset_info = metadata.dataset or {}

    total_samples = int(summary.get("total_samples", len(metadata.samples)) or 0)
    invalid_count = int(summary.get("invalid_samples", 0) or 0)
    valid_image = int(summary.get("valid_image_samples", summary.get("valid_samples", 0)) or 0)
    valid_pose = int(summary.get("valid_pose_samples", 0) or 0)
    valid_quality = int(summary.get("valid_quality_samples", 0) or 0)
    usable_pose = int(summary.get("usable_pose_samples", summary.get("usable_for_sampling", 0)) or 0)
    usable_quality = int(summary.get("usable_quality_samples", 0) or 0)

    elapsed_clean = max(0.0, float(elapsed_seconds))
    if elapsed_clean <= 0.0:
        throughput = 0.0
    else:
        throughput = float(total_samples) / elapsed_clean
    if not math.isfinite(throughput):
        throughput = 0.0
    throughput = round(throughput, 2)

    invalid_details = []
    for s in metadata.samples:
        if is_record_summary_invalid(s) or (s.get("issues") or []):
            if is_record_summary_invalid(s) or (s.get("issues") or []):
                invalid_details.append({
                    "sample_id": s.get("sample_id"),
                    "sample_key": s.get("sample_key"),
                    "issues": list(s.get("issues") or []),
                })
                if len(invalid_details) >= max_json_issues:
                    break

    warnings: List[str] = []
    if invalid_count > 0:
        warnings.append(f"invalid_samples={invalid_count}")
    if int(stale_signature_count or 0) > 0:
        warnings.append(f"stale_signature_count={int(stale_signature_count)}")
    if int(signature_upgraded_count or 0) > 0:
        warnings.append(f"signature_upgraded_count={int(signature_upgraded_count)}")

    report = AnalyzerReport(
        created_at=datetime.now(timezone.utc).isoformat(),
        faceset_format=faceset_format,
        dataset_path=str(dataset_path),
        dataset_fingerprint=dataset_info.get("fingerprint"),
        total_samples=total_samples,
        valid_image_samples=valid_image,
        valid_pose_samples=valid_pose,
        valid_quality_samples=valid_quality,
        usable_pose_samples=usable_pose,
        usable_quality_samples=usable_quality,
        usable_for_sampling=usable_pose,
        invalid_samples=invalid_count,
        elapsed_time_seconds=round(elapsed_clean, 3),
        throughput_samples_per_sec=throughput,
        incremental=incremental,
        reused_count=int(reused_count or 0),
        recomputed_count=int(recomputed_count or 0),
        added_count=int(added_count or 0),
        removed_count=int(removed_count or 0),
        stale_signature_count=int(stale_signature_count or 0),
        signature_upgraded_count=int(signature_upgraded_count or 0),
        pose_distribution_yaw=dict(
            summary.get("yaw_bucket_counts") or summary.get("pose_distribution_yaw") or {}
        ),
        pose_distribution_pitch=dict(
            summary.get("pitch_bucket_counts") or summary.get("pose_distribution_pitch") or {}
        ),
        quality_stats=dict(summary.get("quality_stats") or {}),
        unknown_yaw_count=int(summary.get("unknown_yaw_count", 0) or 0),
        unknown_pitch_count=int(summary.get("unknown_pitch_count", 0) or 0),
        invalid_samples_detail=invalid_details,
        warnings=warnings,
    )

    return report


def print_console_summary(report: AnalyzerReport, max_console_issues: int = 10) -> None:
    """Print clean summary to console via core.interact.io."""
    io.log_info("================ Faceset Analysis Summary ================")
    io.log_info(f"Dataset Path      : {report.dataset_path}")
    io.log_info(f"Faceset Format    : {report.faceset_format}")
    io.log_info(f"Dataset Fingerprint: {report.dataset_fingerprint or 'N/A'}")
    io.log_info(f"Total Samples     : {report.total_samples}")
    io.log_info(
        f"Valid Image/Pose/Quality : {report.valid_image_samples}/"
        f"{report.valid_pose_samples}/{report.valid_quality_samples}"
    )
    io.log_info(
        f"Usable Pose/Quality: {report.usable_pose_samples}/{report.usable_quality_samples}"
    )
    io.log_info(f"Invalid Samples   : {report.invalid_samples}")
    io.log_info(
        f"Time Elapsed      : {report.elapsed_time_seconds}s "
        f"({report.throughput_samples_per_sec} samples/sec)"
    )

    if report.incremental:
        io.log_info(
            f"Incremental Stats : Reused={report.reused_count}, "
            f"Recomputed={report.recomputed_count}, Added={report.added_count}, "
            f"Removed={report.removed_count}, StaleSig={report.stale_signature_count}"
        )

    io.log_info("--- Pose Distribution (Yaw) ---")
    for bucket, count in report.pose_distribution_yaw.items():
        io.log_info(f"  {bucket:<25}: {count}")

    if report.invalid_samples > 0:
        io.log_info(f"--- Invalid Samples Preview (Top {max_console_issues}) ---")
        for idx, item in enumerate(report.invalid_samples_detail[:max_console_issues]):
            io.log_info(
                f"  [{idx + 1}] Key: {item.get('sample_key')} | "
                f"Issues: {', '.join(item.get('issues', []))}"
            )
        if len(report.invalid_samples_detail) > max_console_issues:
            io.log_info(
                f"  ... and {len(report.invalid_samples_detail) - max_console_issues} more."
            )

    io.log_info(f"Note: {report.disclaimer}")
    io.log_info("==========================================================")


def save_report_json(report: AnalyzerReport, report_path: Path) -> None:
    """Save machine report JSON file."""
    report_path = Path(report_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, ensure_ascii=False, indent=2, allow_nan=False)
