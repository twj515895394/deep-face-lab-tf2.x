import math
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Optional


class SamplingMode(Enum):
    LEGACY = "legacy"
    LEGACY_RANDOM = "legacy_random"
    LEGACY_UNIFORM_YAW = "legacy_uniform_yaw"
    POSE_BALANCED = "pose_balanced"
    QUALITY_POSE_BALANCED = "quality_pose_balanced"


@dataclass(frozen=True)
class SamplingConfig:
    mode: SamplingMode = SamplingMode.LEGACY
    metadata_path: Optional[str] = None
    fallback_mode: SamplingMode = SamplingMode.LEGACY_RANDOM
    pose_balance_strength: float = 0.5
    quality_strength: float = 0.5
    uniform_mix: float = 0.1
    min_sample_weight: float = 0.5
    max_sample_weight: float = 2.0
    min_metadata_match_ratio: float = 0.90
    seed: Optional[int] = None
    log_interval_draws: int = 10000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "metadata_path": self.metadata_path,
            "fallback_mode": self.fallback_mode.value,
            "pose_balance_strength": self.pose_balance_strength,
            "quality_strength": self.quality_strength,
            "uniform_mix": self.uniform_mix,
            "min_sample_weight": self.min_sample_weight,
            "max_sample_weight": self.max_sample_weight,
            "min_metadata_match_ratio": self.min_metadata_match_ratio,
            "seed": self.seed,
            "log_interval_draws": self.log_interval_draws,
        }

    @classmethod
    def from_mapping(cls, raw: Optional[Dict[str, Any]]) -> "SamplingConfig":
        if not isinstance(raw, dict):
            return cls()

        def _safe_float(val: Any, default: float, v_min: float = 0.0, v_max: float = 1.0) -> float:
            try:
                f_val = float(val)
                if not math.isfinite(f_val):
                    return default
                return float(max(v_min, min(v_max, f_val)))
            except (ValueError, TypeError):
                return default

        # Mode parsing
        mode_val = raw.get("mode", SamplingMode.LEGACY.value)
        try:
            parsed_mode = SamplingMode(mode_val)
        except ValueError:
            parsed_mode = SamplingMode.LEGACY

        metadata_path_raw = raw.get("metadata_path")
        metadata_path = str(metadata_path_raw) if metadata_path_raw is not None else None

        # Fallback mode parsing (only allow legacy_random or legacy_uniform_yaw)
        fb_val = raw.get("fallback_mode", SamplingMode.LEGACY_RANDOM.value)
        try:
            parsed_fb = SamplingMode(fb_val)
            if parsed_fb not in (SamplingMode.LEGACY_RANDOM, SamplingMode.LEGACY_UNIFORM_YAW):
                parsed_fb = SamplingMode.LEGACY_RANDOM
        except ValueError:
            parsed_fb = SamplingMode.LEGACY_RANDOM

        pose_balance_strength = _safe_float(raw.get("pose_balance_strength"), 0.5, 0.0, 1.0)
        quality_strength = _safe_float(raw.get("quality_strength"), 0.5, 0.0, 1.0)
        uniform_mix = _safe_float(raw.get("uniform_mix"), 0.1, 0.0, 1.0)
        min_match_ratio = _safe_float(raw.get("min_metadata_match_ratio"), 0.90, 0.0, 1.0)

        min_weight = _safe_float(raw.get("min_sample_weight"), 0.5, 0.01, 100.0)
        max_weight = _safe_float(raw.get("max_sample_weight"), 2.0, 0.01, 100.0)

        if min_weight > max_weight:
            min_weight = 0.5
            max_weight = 2.0

        seed_raw = raw.get("seed")
        try:
            seed = int(seed_raw) if seed_raw is not None else None
        except (ValueError, TypeError):
            seed = None

        log_interval_raw = raw.get("log_interval_draws", 10000)
        try:
            log_interval = max(100, int(log_interval_raw))
        except (ValueError, TypeError):
            log_interval = 10000

        return cls(
            mode=parsed_mode,
            metadata_path=metadata_path,
            fallback_mode=parsed_fb,
            pose_balance_strength=pose_balance_strength,
            quality_strength=quality_strength,
            uniform_mix=uniform_mix,
            min_sample_weight=min_weight,
            max_sample_weight=max_weight,
            min_metadata_match_ratio=min_match_ratio,
            seed=seed,
            log_interval_draws=log_interval,
        )
