""" Backward-compatible enhancement feature flags.

所有增强默认关闭；解析失败时返回安全默认值，避免旧模型和传统 Merge 路径被新配置影响。
"""

from __future__ import annotations

import copy
import warnings
from typing import Any, Dict, List, Mapping, Optional, Sequence

from samplelib.sampling.config import (
    SamplingConfig,
    parse_role_sampling_configs,
)


SUPPORTED_SCHEMA_VERSION = 1

# Top-level JSON keys that must live under "enhancements", never at options root.
BATCH2_TOP_LEVEL_MISPLACED_KEYS = ("training", "sampling", "runtime")


DEFAULT_ENHANCEMENT_CONFIG = {
    "schema_version": SUPPORTED_SCHEMA_VERSION,
    "training": {
        "enabled": False,
        "metadata_sampling": False,
        "loss_hooks": False,
        "identity_geometry": False,
        "curriculum": False,
    },
    "merge": {
        "enabled": False,
        "source_shape_template": False,
        "shape_aware_warp": False,
        "shape_aware_mask": False,
        "temporal_stabilization": False,
    },
    "runtime": {
        "fallback_on_optional_error": True,
        "strict_validation": False,
    },
    "sampling": SamplingConfig().to_dict(),
}


def _safe_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("1", "true", "yes", "y", "on"):
            return True
        if text in ("0", "false", "no", "n", "off"):
            return False
    return default


def detect_misplaced_batch2_top_level_keys(options_mapping: Any) -> List[str]:
    """Return Batch 2 keys found at options root (must be under enhancements)."""
    if not isinstance(options_mapping, Mapping):
        return []
    found = [key for key in BATCH2_TOP_LEVEL_MISPLACED_KEYS if key in options_mapping]
    return found


def format_misplaced_batch2_keys_warning(keys: Sequence[str]) -> str:
    key_list = ", ".join(keys)
    return (
        f'Unsupported top-level Batch 2 config keys detected: {key_list}. '
        f'Expected under "enhancements".'
    )


class EnhancementConfig:
    def __init__(
        self,
        schema_version: int = SUPPORTED_SCHEMA_VERSION,
        training: Optional[Mapping[str, Any]] = None,
        merge: Optional[Mapping[str, Any]] = None,
        runtime: Optional[Mapping[str, Any]] = None,
        sampling: Optional[Mapping[str, Any]] = None,
        extra_fields: Optional[Mapping[str, Any]] = None,
        config_warnings: Optional[Sequence[str]] = None,
    ):
        self.schema_version = schema_version
        self._training = copy.deepcopy(DEFAULT_ENHANCEMENT_CONFIG["training"])
        self._merge = copy.deepcopy(DEFAULT_ENHANCEMENT_CONFIG["merge"])
        self._runtime = copy.deepcopy(DEFAULT_ENHANCEMENT_CONFIG["runtime"])
        self._extra_fields = copy.deepcopy(dict(extra_fields or {}))
        self._unsupported_schema = schema_version > SUPPORTED_SCHEMA_VERSION
        self._config_warnings: List[str] = list(config_warnings or [])
        self._side_sampling: Dict[str, SamplingConfig] = {}
        self._sampling_layout = "empty"
        self._base_has_explicit_fields = False

        if self._unsupported_schema:
            warnings.warn(
                "Unsupported enhancement schema_version; all enhancements disabled.",
                UserWarning,
            )
            self._sampling_config = SamplingConfig()
            return

        self._merge_section(self._training, training)
        self._merge_section(self._merge, merge)
        self._merge_section(self._runtime, runtime)

        base_cfg, side_cfgs, sampling_warnings, layout = parse_role_sampling_configs(
            dict(sampling) if isinstance(sampling, Mapping) else sampling
        )
        self._config_warnings.extend(sampling_warnings)
        self._sampling_config = base_cfg
        self._side_sampling = side_cfgs
        self._sampling_layout = layout
        if isinstance(sampling, Mapping):
            self._base_has_explicit_fields = any(
                k not in ("src", "dst") for k in sampling.keys()
            )

    @staticmethod
    def _merge_section(target: Dict[str, Any], source: Optional[Mapping[str, Any]]) -> None:
        if not isinstance(source, Mapping):
            return
        for key, value in source.items():
            if key in target and isinstance(target[key], bool):
                target[key] = _safe_bool(value, target[key])
            # Section 内未知字段必须忽略，避免旧代码未来误查 unknown flag 时被意外启用。

    @classmethod
    def from_mapping(cls, raw_mapping: Any) -> "EnhancementConfig":
        if isinstance(raw_mapping, EnhancementConfig):
            return raw_mapping
        if not isinstance(raw_mapping, Mapping):
            return cls()
        try:
            schema_version = raw_mapping.get("schema_version", SUPPORTED_SCHEMA_VERSION)
            try:
                schema_version = int(schema_version)
            except (TypeError, ValueError):
                schema_version = SUPPORTED_SCHEMA_VERSION

            known = {"schema_version", "training", "merge", "runtime", "sampling"}
            extra_fields = {
                key: copy.deepcopy(value)
                for key, value in raw_mapping.items()
                if key not in known
            }
            return cls(
                schema_version=schema_version,
                training=raw_mapping.get("training"),
                merge=raw_mapping.get("merge"),
                runtime=raw_mapping.get("runtime"),
                sampling=raw_mapping.get("sampling"),
                extra_fields=extra_fields,
            )
        except Exception:
            return cls()

    @property
    def training_enabled(self) -> bool:
        return False if self._unsupported_schema else bool(self._training.get("enabled", False))

    @property
    def merge_enabled(self) -> bool:
        return False if self._unsupported_schema else bool(self._merge.get("enabled", False))

    @property
    def fallback_on_optional_error(self) -> bool:
        return bool(self._runtime.get("fallback_on_optional_error", True))

    @property
    def strict_validation(self) -> bool:
        return bool(self._runtime.get("strict_validation", False))

    @property
    def sampling_config(self) -> SamplingConfig:
        """Base/global SamplingConfig (legacy callers). Prefer sampling_config_for(role)."""
        return self._sampling_config

    @property
    def config_warnings(self) -> List[str]:
        return list(self._config_warnings)

    def config_warnings_for(self, role: str) -> List[str]:
        """Return warnings visible for a faceset role (R1-04).

        - global warnings (no ``sampling.src:`` / ``sampling.dst:`` prefix) → both sides
        - ``sampling.src:`` → src only
        - ``sampling.dst:`` → dst only
        """
        role_key = str(role).strip().lower()
        if role_key not in ("src", "dst"):
            raise ValueError(f"Unknown sampling role {role!r}; expected 'src' or 'dst'")
        prefix_src = "sampling.src:"
        prefix_dst = "sampling.dst:"
        visible: List[str] = []
        for warn in self._config_warnings:
            text = str(warn)
            if text.startswith(prefix_src):
                if role_key == "src":
                    visible.append(text)
            elif text.startswith(prefix_dst):
                if role_key == "dst":
                    visible.append(text)
            else:
                visible.append(text)
        return visible

    def sampling_config_for(self, role: str) -> SamplingConfig:
        """Resolved SamplingConfig for a faceset role (src|dst).

        Priority: SamplingConfig defaults → flat sampling base → sampling.<role> override.
        Missing side uses base; never copies the other side automatically.
        """
        role_key = str(role).strip().lower()
        if role_key not in ("src", "dst"):
            raise ValueError(f"Unknown sampling role {role!r}; expected 'src' or 'dst'")
        if role_key in self._side_sampling:
            return self._side_sampling[role_key]
        return self._sampling_config

    def sampling_config_source(self, role: str) -> str:
        """Human-readable provenance of the resolved side config for startup logs."""
        role_key = str(role).strip().lower()
        if role_key not in ("src", "dst"):
            raise ValueError(f"Unknown sampling role {role!r}; expected 'src' or 'dst'")
        has_side = role_key in self._side_sampling
        has_base = self._base_has_explicit_fields
        if has_side and has_base:
            return f"base+{role_key}_override"
        if has_side:
            return f"{role_key}_override"
        if has_base:
            return "base"
        return "default"

    def metadata_sampling_gate_state(self) -> Dict[str, Any]:
        """Expose dual-gate flags for logging and tests."""
        enabled = bool(self._training.get("enabled", False)) and not self._unsupported_schema
        meta = bool(self._training.get("metadata_sampling", False)) and not self._unsupported_schema
        both = enabled and meta
        return {
            "training_enabled": enabled,
            "metadata_sampling": meta,
            "open": both,
        }

    def is_enabled(self, path: str) -> bool:
        if self._unsupported_schema or not isinstance(path, str) or not path:
            return False
        section, _, name = path.partition(".")
        if section == "training":
            if not self.training_enabled:
                return False
            return True if not name else bool(self._training.get(name, False))
        if section == "merge":
            if not self.merge_enabled:
                return False
            return True if not name else bool(self._merge.get(name, False))
        if section == "runtime":
            return True if not name else bool(self._runtime.get(name, False))
        return False

    def to_dict(self) -> Dict[str, Any]:
        sampling_out = self._sampling_config.to_dict()
        # Persist resolved side configs so roundtrip keeps src/dst overrides.
        for role in ("src", "dst"):
            if role in self._side_sampling:
                sampling_out[role] = self._side_sampling[role].to_dict()

        result = {
            "schema_version": self.schema_version,
            "training": copy.deepcopy(self._training),
            "merge": copy.deepcopy(self._merge),
            "runtime": copy.deepcopy(self._runtime),
            "sampling": sampling_out,
        }
        result.update(copy.deepcopy(self._extra_fields))
        return result


def normalize_enhancement_config(raw_mapping: Any) -> EnhancementConfig:
    return EnhancementConfig.from_mapping(raw_mapping)


def apply_interactive_sampling_base_update(
    enhancements_dict: Mapping[str, Any],
    *,
    enable_meta_sampling: bool,
    chosen_base_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """Update training gates + base sampling mode without dropping src/dst (R1-03).

    Traditional interactive Override only edits base fields. Side overrides must be
    preserved so re-enabling the dual gate restores the previous side config.
    """
    updated = copy.deepcopy(dict(enhancements_dict))
    sampling = copy.deepcopy(updated.get("sampling") or {})
    if not isinstance(sampling, dict):
        sampling = {}

    if enable_meta_sampling:
        if chosen_base_mode is not None:
            sampling["mode"] = chosen_base_mode
    else:
        sampling["mode"] = "legacy"

    training = copy.deepcopy(updated.get("training") or {})
    if not isinstance(training, dict):
        training = {}
    training["enabled"] = bool(enable_meta_sampling)
    training["metadata_sampling"] = bool(enable_meta_sampling)

    updated["training"] = training
    updated["sampling"] = sampling
    return updated
