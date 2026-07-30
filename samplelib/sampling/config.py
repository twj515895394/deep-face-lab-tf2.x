import math
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


class SamplingMode(Enum):
    LEGACY = "legacy"
    LEGACY_RANDOM = "legacy_random"
    LEGACY_UNIFORM_YAW = "legacy_uniform_yaw"
    POSE_BALANCED = "pose_balanced"
    QUALITY_POSE_BALANCED = "quality_pose_balanced"


# Flat SamplingConfig field names (side keys src/dst are handled by EnhancementConfig).
SAMPLING_CONFIG_FIELD_KEYS = frozenset({
    "mode",
    "metadata_path",
    "fallback_mode",
    "pose_balance_strength",
    "quality_strength",
    "uniform_mix",
    "min_sample_weight",
    "max_sample_weight",
    "min_metadata_match_ratio",
    "seed",
    "log_interval_draws",
})

SAMPLING_SIDE_KEYS = frozenset({"src", "dst"})
LEGACY_FALLBACK_MODES = frozenset({
    SamplingMode.LEGACY_RANDOM,
    SamplingMode.LEGACY_UNIFORM_YAW,
})


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

    def with_seed(self, seed: Optional[int]) -> "SamplingConfig":
        """Return a copy with seed replaced (does not mutate frozen instance)."""
        return SamplingConfig(
            mode=self.mode,
            metadata_path=self.metadata_path,
            fallback_mode=self.fallback_mode,
            pose_balance_strength=self.pose_balance_strength,
            quality_strength=self.quality_strength,
            uniform_mix=self.uniform_mix,
            min_sample_weight=self.min_sample_weight,
            max_sample_weight=self.max_sample_weight,
            min_metadata_match_ratio=self.min_metadata_match_ratio,
            seed=seed,
            log_interval_draws=self.log_interval_draws,
        )

    @classmethod
    def from_mapping(
        cls,
        raw: Optional[Dict[str, Any]],
        warnings_out: Optional[List[str]] = None,
    ) -> "SamplingConfig":
        """Parse a flat sampling mapping (no src/dst nesting).

        Unknown field names are reported via warnings_out when provided.
        Invalid values fall back to safe defaults (legacy-safe).
        """
        if not isinstance(raw, dict):
            return cls()

        def _warn(msg: str) -> None:
            if warnings_out is not None:
                warnings_out.append(msg)

        for key in raw.keys():
            if key in SAMPLING_SIDE_KEYS:
                continue
            if key not in SAMPLING_CONFIG_FIELD_KEYS:
                _warn(f"Unknown sampling field ignored: {key}")

        def _safe_float(val: Any, default: float, v_min: float = 0.0, v_max: float = 1.0) -> float:
            try:
                f_val = float(val)
                if not math.isfinite(f_val):
                    return default
                return float(max(v_min, min(v_max, f_val)))
            except (ValueError, TypeError):
                return default

        mode_val = raw.get("mode", SamplingMode.LEGACY.value)
        try:
            parsed_mode = SamplingMode(mode_val)
        except ValueError:
            _warn(f"Invalid sampling mode {mode_val!r}; using legacy")
            parsed_mode = SamplingMode.LEGACY

        metadata_path_raw = raw.get("metadata_path")
        metadata_path = str(metadata_path_raw) if metadata_path_raw is not None else None

        fb_val = raw.get("fallback_mode", SamplingMode.LEGACY_RANDOM.value)
        try:
            parsed_fb = SamplingMode(fb_val)
            if parsed_fb not in LEGACY_FALLBACK_MODES:
                _warn(
                    f"Invalid fallback_mode {fb_val!r}; only legacy_random/"
                    "legacy_uniform_yaw allowed"
                )
                parsed_fb = SamplingMode.LEGACY_RANDOM
        except ValueError:
            _warn(f"Invalid fallback_mode {fb_val!r}; using legacy_random")
            parsed_fb = SamplingMode.LEGACY_RANDOM

        pose_balance_strength = _safe_float(raw.get("pose_balance_strength"), 0.5, 0.0, 1.0)
        quality_strength = _safe_float(raw.get("quality_strength"), 0.5, 0.0, 1.0)
        uniform_mix = _safe_float(raw.get("uniform_mix"), 0.1, 0.0, 1.0)
        min_match_ratio = _safe_float(raw.get("min_metadata_match_ratio"), 0.90, 0.0, 1.0)

        min_weight = _safe_float(raw.get("min_sample_weight"), 0.5, 0.01, 100.0)
        max_weight = _safe_float(raw.get("max_sample_weight"), 2.0, 0.01, 100.0)

        if min_weight > max_weight:
            _warn("min_sample_weight > max_sample_weight; using defaults 0.5/2.0")
            min_weight = 0.5
            max_weight = 2.0

        seed_raw = raw.get("seed")
        try:
            seed = int(seed_raw) if seed_raw is not None else None
        except (ValueError, TypeError):
            _warn(f"Invalid seed {seed_raw!r}; using None")
            seed = None

        log_interval_raw = raw.get("log_interval_draws", 10000)
        try:
            log_interval = max(100, int(log_interval_raw))
        except (ValueError, TypeError):
            _warn(f"Invalid log_interval_draws {log_interval_raw!r}; using 10000")
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


def resolve_metadata_path(samples_path: Any, configured_path: Optional[str]) -> Path:
    """Resolve metadata path relative to a faceset root with escape protection.

    Rules:
    - None / empty → <faceset>/faceset_metadata.v1.json
    - absolute path → allowed as-is (caller must log resolved path)
    - relative path → resolved under faceset root; must not escape root
    - ``..`` escape raises ValueError (config error, not missing-metadata fallback)
    """
    root = Path(samples_path)
    try:
        root_resolved = root.resolve()
    except OSError:
        root_resolved = root

    if configured_path is None:
        return root_resolved / "faceset_metadata.v1.json"

    text = str(configured_path).strip()
    if text == "":
        return root_resolved / "faceset_metadata.v1.json"

    candidate = Path(text)
    if candidate.is_absolute():
        try:
            return candidate.resolve()
        except OSError:
            return candidate

    try:
        resolved = (root_resolved / candidate).resolve()
    except OSError as exc:
        raise ValueError(
            f"metadata_path cannot be resolved under faceset root: {configured_path!r}"
        ) from exc

    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(
            f"metadata_path escapes faceset root: {configured_path!r}"
        ) from exc

    return resolved


def split_sampling_mapping(
    raw: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    """Split sampling mapping into flat base fields and side override dicts.

    Returns:
        base_raw: flat fields only
        side_raw: role -> mapping (only valid mapping sides)
        warnings: human-readable validation warnings
    """
    warnings: List[str] = []
    if not isinstance(raw, dict):
        if raw is not None:
            warnings.append("sampling must be a JSON object; using defaults")
        return {}, {}, warnings

    base_raw: Dict[str, Any] = {}
    side_raw: Dict[str, Any] = {}
    for key, value in raw.items():
        if key in SAMPLING_SIDE_KEYS:
            if not isinstance(value, dict):
                warnings.append(
                    f"Invalid sampling.{key} type {type(value).__name__}; "
                    f"expected object, side ignored"
                )
                continue
            side_raw[key] = dict(value)
        else:
            base_raw[key] = value
    return base_raw, side_raw, warnings


def merge_sampling_configs(
    base: SamplingConfig,
    override: Optional[Dict[str, Any]],
    warnings_out: Optional[List[str]] = None,
) -> SamplingConfig:
    """Apply side override fields onto a base SamplingConfig (defaults → base → side)."""
    if not override:
        return base
    merged = base.to_dict()
    merged.update(override)
    return SamplingConfig.from_mapping(merged, warnings_out=warnings_out)


def parse_role_sampling_configs(
    raw: Optional[Dict[str, Any]],
) -> Tuple[SamplingConfig, Dict[str, SamplingConfig], List[str], str]:
    """Parse full sampling mapping into base + per-role resolved configs.

    Returns:
        base_config, side_configs (resolved), warnings, description of layout
        layout is one of: empty | base | sides | base+sides
    """
    base_raw, side_raw, warnings = split_sampling_mapping(raw)
    base = SamplingConfig.from_mapping(base_raw, warnings_out=warnings)

    sides: Dict[str, SamplingConfig] = {}
    for role, override in side_raw.items():
        sides[role] = merge_sampling_configs(base, override, warnings_out=warnings)

    if base_raw and sides:
        layout = "base+sides"
    elif sides:
        layout = "sides"
    elif base_raw:
        layout = "base"
    else:
        layout = "empty"

    return base, sides, warnings, layout
