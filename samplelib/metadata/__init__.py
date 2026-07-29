"""
Batch 2 Metadata Package
Provides Sample Identity, Dataset Fingerprint, and Schema V1 specification.
"""

from .identity import build_sample_id, build_sample_key, normalize_sample_path
from .fingerprint import SampleSignature, build_dataset_fingerprint, build_sample_signature
from .schema import FacesetMetadataV1, MetadataValidationResult, MetadataValidationIssue, sanitize_finite_json
from .pose import FacesetPoseConfig, PoseAnalysisResult, analyze_pose, validate_landmarks, assign_yaw_bucket, assign_pitch_bucket
from .quality import FacesetQualityConfig, ImageValidation, RawQualityMetrics, validate_image, compute_raw_quality, finalize_quality_scores
from .analyzer import FacesetAnalyzer, FacesetAnalyzerConfig, AnalyzerResult

__all__ = [
    "build_sample_key",
    "build_sample_id",
    "normalize_sample_path",
    "SampleSignature",
    "build_sample_signature",
    "build_dataset_fingerprint",
    "FacesetMetadataV1",
    "MetadataValidationResult",
    "MetadataValidationIssue",
    "sanitize_finite_json",
    "FacesetPoseConfig",
    "PoseAnalysisResult",
    "analyze_pose",
    "validate_landmarks",
    "assign_yaw_bucket",
    "assign_pitch_bucket",
    "FacesetQualityConfig",
    "ImageValidation",
    "RawQualityMetrics",
    "validate_image",
    "compute_raw_quality",
    "finalize_quality_scores",
    "FacesetAnalyzer",
    "FacesetAnalyzerConfig",
    "AnalyzerResult",
]

