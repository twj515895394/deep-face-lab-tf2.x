"""Backward-compatible enhancement feature flags.

所有增强默认关闭；解析失败时返回安全默认值，避免旧模型和传统 Merge 路径被新配置影响。
"""

from __future__ import annotations

import copy
import warnings
from typing import Any, Dict, Mapping, Optional


SUPPORTED_SCHEMA_VERSION = 1


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


class EnhancementConfig:
    def __init__(
        self,
        schema_version: int = SUPPORTED_SCHEMA_VERSION,
        training: Optional[Mapping[str, Any]] = None,
        merge: Optional[Mapping[str, Any]] = None,
        runtime: Optional[Mapping[str, Any]] = None,
        extra_fields: Optional[Mapping[str, Any]] = None,
    ):
        self.schema_version = schema_version
        self._training = copy.deepcopy(DEFAULT_ENHANCEMENT_CONFIG["training"])
        self._merge = copy.deepcopy(DEFAULT_ENHANCEMENT_CONFIG["merge"])
        self._runtime = copy.deepcopy(DEFAULT_ENHANCEMENT_CONFIG["runtime"])
        self._extra_fields = copy.deepcopy(dict(extra_fields or {}))
        self._unsupported_schema = schema_version > SUPPORTED_SCHEMA_VERSION

        if self._unsupported_schema:
            warnings.warn(
                "Unsupported enhancement schema_version; all enhancements disabled.",
                UserWarning,
            )
            return

        self._merge_section(self._training, training)
        self._merge_section(self._merge, merge)
        self._merge_section(self._runtime, runtime)

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

            known = {"schema_version", "training", "merge", "runtime"}
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
        result = {
            "schema_version": self.schema_version,
            "training": copy.deepcopy(self._training),
            "merge": copy.deepcopy(self._merge),
            "runtime": copy.deepcopy(self._runtime),
        }
        result.update(copy.deepcopy(self._extra_fields))
        return result


def normalize_enhancement_config(raw_mapping: Any) -> EnhancementConfig:
    return EnhancementConfig.from_mapping(raw_mapping)
