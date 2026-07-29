import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


@dataclass
class ImageValidation:
    valid: bool
    height: Optional[int] = None
    width: Optional[int] = None
    channels: Optional[int] = None
    issues: List[str] = field(default_factory=list)


@dataclass
class RawQualityMetrics:
    valid: bool
    sharpness_raw: Optional[float] = None
    dark_ratio: Optional[float] = None
    bright_ratio: Optional[float] = None
    exposure_score: Optional[float] = None
    issues: List[str] = field(default_factory=list)


@dataclass
class FacesetQualityConfig:
    dark_threshold: int = 15
    bright_threshold: int = 240
    sharpness_weight: float = 0.7
    exposure_weight: float = 0.3
    p_low: float = 5.0
    p_high: float = 95.0


def validate_image(bgr_img: Optional[np.ndarray]) -> ImageValidation:
    """
    Validate BGR image array properties.
    Expects non-empty 3-channel (H, W, 3) image array.
    """
    if bgr_img is None:
        return ImageValidation(valid=False, issues=["MISSING_IMAGE_DATA"])

    if not isinstance(bgr_img, np.ndarray):
        return ImageValidation(valid=False, issues=["INVALID_IMAGE_TYPE"])

    if len(bgr_img.shape) != 3 or bgr_img.shape[2] != 3:
        return ImageValidation(valid=False, issues=[f"INVALID_IMAGE_SHAPE_{bgr_img.shape}"])

    h, w, c = bgr_img.shape
    if h <= 0 or w <= 0:
        return ImageValidation(valid=False, height=h, width=w, channels=c, issues=["ZERO_IMAGE_DIMENSION"])

    if not np.isfinite(bgr_img).all():
        return ImageValidation(valid=False, height=h, width=w, channels=c, issues=["NON_FINITE_PIXELS"])

    return ImageValidation(valid=True, height=h, width=w, channels=c)


def compute_raw_quality(bgr_img: np.ndarray, config: Optional[FacesetQualityConfig] = None) -> RawQualityMetrics:
    """
    Compute raw (unnormalized) sharpness and exposure metrics from BGR image.
    """
    if config is None:
        config = FacesetQualityConfig()

    val = validate_image(bgr_img)
    if not val.valid:
        return RawQualityMetrics(valid=False, issues=val.issues)

    try:
        # Convert BGR to Grayscale for sharpness and exposure evaluation
        if bgr_img.dtype != np.uint8:
            img_uint8 = np.clip(bgr_img, 0, 255).astype(np.uint8)
        else:
            img_uint8 = bgr_img

        gray = cv2.cvtColor(img_uint8, cv2.COLOR_BGR2GRAY)

        # Sharpness: Variance of Laplacian
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if not math.isfinite(laplacian_var):
            laplacian_var = 0.0

        # Exposure: Ratios of severely dark or clipped bright pixels
        total_pixels = float(gray.size)
        dark_count = float(np.sum(gray <= config.dark_threshold))
        bright_count = float(np.sum(gray >= config.bright_threshold))

        dark_ratio = float(dark_count / total_pixels)
        bright_ratio = float(bright_count / total_pixels)
        exposure_score = float(max(0.0, 1.0 - (dark_ratio + bright_ratio)))

        return RawQualityMetrics(
            valid=True,
            sharpness_raw=laplacian_var,
            dark_ratio=dark_ratio,
            bright_ratio=bright_ratio,
            exposure_score=exposure_score,
        )
    except Exception as e:
        return RawQualityMetrics(valid=False, issues=[f"RAW_QUALITY_COMPUTATION_ERROR_{type(e).__name__}"])


def finalize_quality_scores(
    raw_records: List[Dict],
    config: Optional[FacesetQualityConfig] = None
) -> Tuple[List[Dict], Dict]:
    """
    Pass 2 normalization across all samples in the faceset dataset.
    Computes robust log1p percentile bounds (p05, p95) for sharpness and blends quality_score.
    """
    if config is None:
        config = FacesetQualityConfig()

    # Collect valid raw log-sharpness values
    valid_log_sharpness = []
    for r in raw_records:
        q_raw = r.get("quality_raw")
        if q_raw and q_raw.get("valid") and q_raw.get("sharpness_raw") is not None:
            s_raw = max(0.0, float(q_raw["sharpness_raw"]))
            valid_log_sharpness.append(math.log1p(s_raw))

    if len(valid_log_sharpness) > 0:
        p_low = float(np.percentile(valid_log_sharpness, config.p_low))
        p_high = float(np.percentile(valid_log_sharpness, config.p_high))
    else:
        p_low, p_high = 0.0, 1.0

    p_range = p_high - p_low
    summary_norm = {
        "p05_log_sharpness": p_low,
        "p95_log_sharpness": p_high,
        "valid_sample_count": len(valid_log_sharpness),
    }

    finalized_records = []
    for r in raw_records:
        r_copy = dict(r)
        q_raw = r_copy.get("quality_raw")

        if not q_raw or not q_raw.get("valid") or q_raw.get("sharpness_raw") is None:
            r_copy["quality"] = {
                "sharpness_raw": q_raw.get("sharpness_raw") if q_raw else None,
                "sharpness_normalized": 0.5,
                "exposure_score": q_raw.get("exposure_score") if q_raw else None,
                "quality_score": 0.5,  # Fallback neutral quality
            }
        else:
            s_raw = max(0.0, float(q_raw["sharpness_raw"]))
            log_val = math.log1p(s_raw)

            if p_range < 1e-6:
                norm_sharpness = 0.5
            else:
                norm_sharpness = float(np.clip((log_val - p_low) / p_range, 0.0, 1.0))

            exp_score = float(q_raw.get("exposure_score", 0.5))
            q_score = float(np.clip(
                config.sharpness_weight * norm_sharpness + config.exposure_weight * exp_score,
                0.0, 1.0
            ))

            r_copy["quality"] = {
                "sharpness_raw": s_raw,
                "sharpness_normalized": norm_sharpness,
                "exposure_score": exp_score,
                "dark_ratio": q_raw.get("dark_ratio"),
                "bright_ratio": q_raw.get("bright_ratio"),
                "quality_score": q_score,
            }

        finalized_records.append(r_copy)

    return finalized_records, summary_norm
