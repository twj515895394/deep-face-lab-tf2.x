import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from samplelib.metadata.contracts import (
    LEGACY_PITCH_ALIASES,
    LEGACY_YAW_ALIASES,
    is_bool_compatible,
    is_valid_pitch_bucket,
    is_valid_yaw_bucket,
)


SCHEMA_VERSION_CURRENT = 1





@dataclass
class MetadataValidationIssue:
    code: str
    message: str
    sample_key: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "sample_key": self.sample_key,
        }


@dataclass
class MetadataValidationResult:
    is_valid: bool
    is_supported: bool
    issues: List[MetadataValidationIssue] = field(default_factory=list)
    invalid_sample_ids: List[str] = field(default_factory=list)


def sanitize_finite_json(val: Any, issues_log: Optional[List[MetadataValidationIssue]] = None, current_key: Optional[str] = None) -> Any:
    """
    Recursively sanitize data structure for standard JSON serialization.
    Replaces NaN and Inf float values with None (JSON null) and appends a validation issue.
    """
    if isinstance(val, float):
        if math.isnan(val):
            if issues_log is not None:
                issues_log.append(MetadataValidationIssue(
                    code="NON_FINITE_NAN",
                    message="Replaced NaN float with null",
                    sample_key=current_key
                ))
            return None
        elif math.isinf(val):
            if issues_log is not None:
                issues_log.append(MetadataValidationIssue(
                    code="NON_FINITE_INF",
                    message="Replaced Inf float with null",
                    sample_key=current_key
                ))
            return None
        return val
    elif isinstance(val, dict):
        sanitized = {}
        for k, v in val.items():
            key_ctx = current_key or (v.get("sample_key") if isinstance(v, dict) else None)
            sanitized[k] = sanitize_finite_json(v, issues_log, key_ctx)
        return sanitized
    elif isinstance(val, list):
        return [sanitize_finite_json(item, issues_log, current_key) for item in val]
    elif isinstance(val, tuple):
        return [sanitize_finite_json(item, issues_log, current_key) for item in val]
    else:
        return val


@dataclass
class FacesetMetadataV1:
    schema_version: int = SCHEMA_VERSION_CURRENT
    dataset: dict = field(default_factory=dict)
    analysis_config: dict = field(default_factory=dict)
    summary: dict = field(default_factory=dict)
    samples: List[dict] = field(default_factory=list)
    analyzer_version: str = "v1.0"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def from_mapping(cls, raw: Dict[str, Any], strict: bool = False) -> Tuple["FacesetMetadataV1", MetadataValidationResult]:
        """
        Construct FacesetMetadataV1 from mapping with partial fault tolerance.
        Returns metadata instance and MetadataValidationResult.
        """
        issues = []
        invalid_sample_ids = []

        if not isinstance(raw, dict):
            issue = MetadataValidationIssue(code="INVALID_TOP_LEVEL", message="Metadata root must be a dict/mapping")
            return cls(), MetadataValidationResult(is_valid=False, is_supported=False, issues=[issue])

        schema_ver = raw.get("schema_version", SCHEMA_VERSION_CURRENT)
        if not isinstance(schema_ver, int) or schema_ver > SCHEMA_VERSION_CURRENT:
            issue = MetadataValidationIssue(
                code="UNSUPPORTED_SCHEMA_VERSION",
                message=f"Schema version {schema_ver} is unsupported (max supported: {SCHEMA_VERSION_CURRENT})"
            )
            return cls(schema_version=schema_ver), MetadataValidationResult(is_valid=False, is_supported=False, issues=[issue])

        # Clean NaN/Inf
        sanitized_raw = sanitize_finite_json(raw, issues)

        dataset = sanitized_raw.get("dataset", {})
        analysis_config = sanitized_raw.get("analysis_config", {})
        summary = sanitized_raw.get("summary", {})
        raw_samples = sanitized_raw.get("samples", [])

        validated_samples = []
        seen_sample_ids = set()

        if isinstance(raw_samples, list):
            for idx, sample in enumerate(raw_samples):
                if not isinstance(sample, dict):
                    issues.append(MetadataValidationIssue(code="INVALID_SAMPLE_RECORD", message=f"Sample at index {idx} is not a dict"))
                    continue

                sample_key = sample.get("sample_key")
                sample_id = sample.get("sample_id")

                if not sample_key or not sample_id:
                    issues.append(MetadataValidationIssue(code="MISSING_SAMPLE_KEY_OR_ID", message=f"Sample record missing key or ID at index {idx}", sample_key=sample_key))
                    continue

                if sample_id in seen_sample_ids:
                    issues.append(MetadataValidationIssue(code="DUPLICATE_SAMPLE_ID", message=f"Duplicate sample_id detected: {sample_id}", sample_key=sample_key))
                    invalid_sample_ids.append(sample_id)
                    if strict:
                        continue
                seen_sample_ids.add(sample_id)

                if "pose" in sample:
                    pose_info = sample.get("pose")
                    if not isinstance(pose_info, dict):
                        issues.append(MetadataValidationIssue(code="INVALID_POSE_MAPPING", message=f"Sample pose field must be a dict/mapping, got {type(pose_info).__name__}", sample_key=sample_key))
                    else:
                        valid_val = pose_info.get("valid")
                        # None is treated as "missing valid" (not a type error); non-compatible values are rejected.
                        if valid_val is not None and not is_bool_compatible(valid_val):
                            issues.append(MetadataValidationIssue(
                                code="INVALID_POSE_VALID_TYPE",
                                message=f"Sample pose.valid must be boolean-compatible, got {valid_val!r}",
                                sample_key=sample_key,
                            ))

                        y_b = pose_info.get("yaw_bucket")
                        p_b = pose_info.get("pitch_bucket")

                        if isinstance(y_b, str) and y_b.strip() in LEGACY_YAW_ALIASES:
                            issues.append(MetadataValidationIssue(code="LEGACY_YAW_BUCKET_ALIAS", message=f"Legacy yaw_bucket alias used: {y_b} -> {LEGACY_YAW_ALIASES[y_b.strip()]}", sample_key=sample_key))
                        elif y_b is not None and not is_valid_yaw_bucket(y_b):
                            issues.append(MetadataValidationIssue(code="INVALID_YAW_BUCKET", message=f"Unrecognized yaw_bucket: {y_b}", sample_key=sample_key))

                        if isinstance(p_b, str) and p_b.strip() in LEGACY_PITCH_ALIASES:
                            issues.append(MetadataValidationIssue(code="LEGACY_PITCH_BUCKET_ALIAS", message=f"Legacy pitch_bucket alias used: {p_b} -> {LEGACY_PITCH_ALIASES[p_b.strip()]}", sample_key=sample_key))
                        elif p_b is not None and not is_valid_pitch_bucket(p_b):
                            issues.append(MetadataValidationIssue(code="INVALID_PITCH_BUCKET", message=f"Unrecognized pitch_bucket: {p_b}", sample_key=sample_key))

                validated_samples.append(sample)



        instance = cls(
            schema_version=schema_ver,
            dataset=dataset if isinstance(dataset, dict) else {},
            analysis_config=analysis_config if isinstance(analysis_config, dict) else {},
            summary=summary if isinstance(summary, dict) else {},
            samples=validated_samples,
            analyzer_version=sanitized_raw.get("analyzer_version", "v1.0"),
            created_at=sanitized_raw.get("created_at", datetime.now(timezone.utc).isoformat()),
        )

        is_valid = len(issues) == 0
        res = MetadataValidationResult(
            is_valid=is_valid,
            is_supported=True,
            issues=issues,
            invalid_sample_ids=invalid_sample_ids
        )
        return instance, res

    def validate(self) -> MetadataValidationResult:
        """Validate instance fields."""
        raw_dict = self.to_dict()
        _, result = self.from_mapping(raw_dict)
        return result

    def to_dict(self) -> dict:
        issues_log = []
        raw_dict = {
            "schema_version": self.schema_version,
            "analyzer_version": self.analyzer_version,
            "created_at": self.created_at,
            "dataset": self.dataset,
            "analysis_config": self.analysis_config,
            "summary": self.summary,
            "samples": self.samples,
        }
        return sanitize_finite_json(raw_dict, issues_log)

    def dump_json(self, filepath: Path) -> None:
        """Dump sanitized JSON without allow_nan=True for security."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        data_dict = self.to_dict()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data_dict, f, ensure_ascii=False, indent=2, allow_nan=False)

    @classmethod
    def load_json(cls, filepath: Path) -> Tuple["FacesetMetadataV1", MetadataValidationResult]:
        filepath = Path(filepath)
        if not filepath.exists():
            issue = MetadataValidationIssue(code="FILE_NOT_FOUND", message=f"Metadata file not found: {filepath}")
            return cls(), MetadataValidationResult(is_valid=False, is_supported=False, issues=[issue])

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except Exception as e:
            issue = MetadataValidationIssue(code="JSON_PARSE_ERROR", message=f"Failed to parse JSON file {filepath}: {e}")
            return cls(), MetadataValidationResult(is_valid=False, is_supported=False, issues=[issue])

        return cls.from_mapping(raw_data)
