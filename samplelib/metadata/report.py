import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.interact import interact as io
from samplelib.metadata.schema import FacesetMetadataV1


@dataclass
class AnalyzerReport:
    created_at: str
    faceset_format: str
    dataset_path: str
    dataset_fingerprint: Optional[str]
    total_samples: int
    usable_for_sampling: int
    invalid_samples: int
    elapsed_time_seconds: float
    throughput_samples_per_sec: float
    incremental: bool
    reused_count: int
    recomputed_count: int
    added_count: int
    removed_count: int
    pose_distribution_yaw: Dict[str, int]
    pose_distribution_pitch: Dict[str, int]
    issues: List[Dict[str, Any]] = field(default_factory=list)
    invalid_samples_detail: List[Dict[str, Any]] = field(default_factory=list)
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
    max_json_issues: int = 1000,
) -> AnalyzerReport:
    summary = metadata.summary or {}
    dataset_info = metadata.dataset or {}

    total_samples = summary.get("total_samples", len(metadata.samples))
    usable_count = summary.get("usable_for_sampling", 0)
    invalid_count = summary.get("invalid_samples", 0)

    elapsed_clean = max(0.001, float(elapsed_seconds))
    throughput = round(total_samples / elapsed_clean, 2)

    invalid_details = []
    for s in metadata.samples:
        if not s.get("valid", True):
            invalid_details.append({
                "sample_id": s.get("sample_id"),
                "sample_key": s.get("sample_key"),
                "issues": s.get("issues", []),
            })
            if len(invalid_details) >= max_json_issues:
                break

    report = AnalyzerReport(
        created_at=datetime.now(timezone.utc).isoformat(),
        faceset_format=faceset_format,
        dataset_path=str(dataset_path),
        dataset_fingerprint=dataset_info.get("fingerprint"),
        total_samples=total_samples,
        usable_for_sampling=usable_count,
        invalid_samples=invalid_count,
        elapsed_time_seconds=round(elapsed_clean, 3),
        throughput_samples_per_sec=throughput,
        incremental=incremental,
        reused_count=reused_count,
        recomputed_count=recomputed_count,
        added_count=added_count,
        removed_count=removed_count,
        pose_distribution_yaw=summary.get("yaw_bucket_counts") or summary.get("pose_distribution_yaw") or {},
        pose_distribution_pitch=summary.get("pitch_bucket_counts") or summary.get("pose_distribution_pitch") or {},
        invalid_samples_detail=invalid_details,
    )

    return report


def print_console_summary(report: AnalyzerReport, max_console_issues: int = 10) -> None:
    """Print clean summary to console via core.interact.io."""
    io.log_info("================ Faceset Analysis Summary ================")
    io.log_info(f"Dataset Path      : {report.dataset_path}")
    io.log_info(f"Faceset Format    : {report.faceset_format}")
    io.log_info(f"Dataset Fingerprint: {report.dataset_fingerprint or 'N/A'}")
    io.log_info(f"Total Samples     : {report.total_samples}")
    io.log_info(f"Usable Samples    : {report.usable_for_sampling}")
    io.log_info(f"Invalid Samples   : {report.invalid_samples}")
    io.log_info(f"Time Elapsed      : {report.elapsed_time_seconds}s ({report.throughput_samples_per_sec} samples/sec)")

    if report.incremental:
        io.log_info(
            f"Incremental Stats : Reused={report.reused_count}, "
            f"Recomputed={report.recomputed_count}, Added={report.added_count}, Removed={report.removed_count}"
        )

    io.log_info("--- Pose Distribution (Yaw) ---")
    for bucket, count in report.pose_distribution_yaw.items():
        io.log_info(f"  {bucket:<25}: {count}")

    if report.invalid_samples > 0:
        io.log_info(f"--- Invalid Samples Preview (Top {max_console_issues}) ---")
        for idx, item in enumerate(report.invalid_samples_detail[:max_console_issues]):
            io.log_info(f"  [{idx + 1}] Key: {item.get('sample_key')} | Issues: {', '.join(item.get('issues', []))}")
        if len(report.invalid_samples_detail) > max_console_issues:
            io.log_info(f"  ... and {len(report.invalid_samples_detail) - max_console_issues} more invalid samples.")

    io.log_info(f"Note: {report.disclaimer}")
    io.log_info("==========================================================")


def save_report_json(report: AnalyzerReport, report_path: Path) -> None:
    """Save machine report JSON file."""
    report_path = Path(report_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, ensure_ascii=False, indent=2, allow_nan=False)
