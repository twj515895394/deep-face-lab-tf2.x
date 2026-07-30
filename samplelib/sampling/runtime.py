import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Type

import numpy as np

from core.enhancements import EnhancementConfig
from core.interact import interact as io
from samplelib.SampleLoader import SampleLoader, SampleType
from samplelib.metadata.loader import FacesetMetadataLoader, FacesetMetadataStatus, RuntimeMetadata
from samplelib.sampling.config import SamplingConfig, resolve_metadata_path
from samplelib.sampling.factory import SamplingPolicyFactory, SamplingResolution
from samplelib.sampling.policies import SamplingPolicy

_JSON_ERRORS: Tuple[Type[BaseException], ...] = (json.JSONDecodeError,)


@dataclass
class SamplingRuntime:
    role: str
    metadata_runtime: Optional[RuntimeMetadata]
    resolution: SamplingResolution
    startup_log: Dict[str, Any]
    sampling_config: Optional[SamplingConfig] = None

    @property
    def policy(self) -> SamplingPolicy:
        return self.resolution.policy


def _empty_invalid_runtime(reason: str, sample_count: int = 0) -> RuntimeMetadata:
    return RuntimeMetadata(
        status=FacesetMetadataStatus.INVALID_FILE,
        sample_count=int(sample_count),
        matched_count=0,
        matched_ratio=0.0,
        quality_scores=np.array([], dtype=np.float32),
        yaw_bucket_ids=np.array([], dtype=np.int16),
        pitch_bucket_ids=np.array([], dtype=np.int16),
        pose_valid=np.array([], dtype=bool),
        quality_valid=np.array([], dtype=bool),
        metadata_valid=np.array([], dtype=bool),
        fallback_reason=reason,
    )


def build_sampling_runtime(
    role: str,
    samples_path: Path,
    enhancement_config: EnhancementConfig,
    legacy_uniform_yaw: bool = False,
    base_seed: Optional[int] = None,
    sampling_config: Optional[SamplingConfig] = None,
    sampling_config_source: Optional[str] = None,
) -> SamplingRuntime:
    """
    Build SamplingRuntime for src or dst faceset directory.

    Ticket 20: SampleLoader is a core path (never optional-fallback).
    Only Metadata optional states/errors may fallback when configured.
    """
    role_key = str(role).strip().lower()
    if role_key not in ("src", "dst"):
        raise ValueError(f"Unknown sampling role {role!r}; expected 'src' or 'dst'")

    samples_path = Path(samples_path)
    gate = enhancement_config.metadata_sampling_gate_state()
    sampling_enabled = bool(gate["open"])
    fallback_optional = bool(enhancement_config.fallback_on_optional_error)
    strict_validation = bool(enhancement_config.strict_validation)

    if sampling_config is None:
        sampling_cfg = enhancement_config.sampling_config_for(role_key)
        config_source = enhancement_config.sampling_config_source(role_key)
    else:
        sampling_cfg = sampling_config
        config_source = sampling_config_source or "explicit"

    # Side seed wins; otherwise derive from model base seed with distinct SRC/DST offsets.
    if sampling_cfg.seed is None and base_seed is not None:
        role_seed_offset = 1000 if role_key == "src" else 2000
        sampling_cfg = sampling_cfg.with_seed(int(base_seed) + role_seed_offset)

    # metadata_path escape is a configuration error — never treat as missing-metadata fallback.
    requested_metadata_path = resolve_metadata_path(samples_path, sampling_cfg.metadata_path)
    absolute_configured = (
        sampling_cfg.metadata_path is not None
        and Path(str(sampling_cfg.metadata_path)).is_absolute()
    )

    # Dual-gate partial open: metadata_sampling requested but training.enabled is false.
    if gate["metadata_sampling"] and not gate["training_enabled"]:
        io.log_info(
            f"[Sampling][{role_key}] gate warning: training.metadata_sampling=true but "
            f"training.enabled=false; metadata not loaded, using legacy."
        )

    # Per-role warning isolation (R1-04): do not leak src-only issues into dst logs.
    for warn in enhancement_config.config_warnings_for(role_key):
        io.log_info(f"[Sampling][{role_key}] config: {warn}")

    # ------------------------------------------------------------------
    # Phase A — core sample load (never optional fallback)
    # ------------------------------------------------------------------
    samples = None
    sample_count = 0
    if sampling_enabled:
        # Core: empty faceset / FS / loader failures must raise.
        samples = SampleLoader.load(SampleType.FACE, samples_path)
        sample_count = len(samples) if samples is not None else 0
        if sample_count <= 0:
            raise ValueError(
                f"No training samples for role={role_key} path={samples_path}"
            )

    # ------------------------------------------------------------------
    # Phase B — optional Metadata load/validate
    # ------------------------------------------------------------------
    rt_meta: Optional[RuntimeMetadata] = None
    if sampling_enabled:
        try:
            rt_meta = FacesetMetadataLoader.load(
                samples_path=samples_path,
                samples=samples,
                metadata_path=requested_metadata_path,
                min_match_ratio=sampling_cfg.min_metadata_match_ratio,
            )
        except (MemoryError, KeyboardInterrupt, SystemExit):
            raise
        except (OSError, ValueError, TypeError, KeyError) + _JSON_ERRORS as e:
            # Narrow optional Metadata I/O / parse failures only.
            reason = f"metadata_optional_exception:{type(e).__name__}:{e}"
            if strict_validation or not fallback_optional:
                raise ValueError(
                    f"[Sampling][{role_key}] optional Metadata failure "
                    f"(strict={strict_validation}, fallback_on_optional_error={fallback_optional}): {reason}"
                ) from e
            rt_meta = _empty_invalid_runtime(reason, sample_count=sample_count)
        except Exception as e:
            # Programming / unexpected errors must not become legacy sampling.
            raise RuntimeError(
                f"[Sampling][{role_key}] unexpected Metadata loader failure "
                f"(core, not optional): {type(e).__name__}: {e}"
            ) from e

        # Structured optional statuses from loader (missing/invalid/mismatch).
        if rt_meta is not None and rt_meta.status not in (
            FacesetMetadataStatus.LOADED,
            FacesetMetadataStatus.PARTIAL_MATCH,
        ):
            if strict_validation:
                raise ValueError(
                    f"[Sampling][{role_key}] strict_validation rejected Metadata status="
                    f"{rt_meta.status.value} reason={rt_meta.fallback_reason}"
                )
            if not fallback_optional:
                raise ValueError(
                    f"[Sampling][{role_key}] Metadata unavailable status="
                    f"{rt_meta.status.value} reason={rt_meta.fallback_reason}; "
                    "fallback_on_optional_error is False."
                )

    # ------------------------------------------------------------------
    # Phase C — policy resolve (constructor bugs must raise)
    # ------------------------------------------------------------------
    try:
        resolution = SamplingPolicyFactory.resolve(
            config=sampling_cfg,
            metadata_sampling_enabled=sampling_enabled,
            legacy_uniform_yaw=legacy_uniform_yaw,
            runtime_metadata=rt_meta,
            role=role_key,
        )
    except (MemoryError, KeyboardInterrupt, SystemExit):
        raise
    except ValueError as e:
        # Factory may raise ValueError for unusable metadata modes.
        if strict_validation or not fallback_optional:
            raise
        # Optional: fall back to gate-off legacy resolve.
        resolution = SamplingPolicyFactory.resolve(
            config=sampling_cfg,
            metadata_sampling_enabled=False,
            legacy_uniform_yaw=legacy_uniform_yaw,
            runtime_metadata=rt_meta,
            role=role_key,
        )
        if resolution.fallback_reason is None:
            resolution = SamplingResolution(
                requested_mode=resolution.requested_mode,
                effective_mode=resolution.effective_mode,
                fallback_reason=f"policy_resolve_value_error:{e}",
                policy=resolution.policy,
            )
    # Do not catch broad Exception here — host/policy programming errors must propagate.

    if (
        sampling_enabled
        and resolution.fallback_reason
        and not fallback_optional
        and resolution.requested_mode not in ("legacy", "legacy_random", "legacy_uniform_yaw")
    ):
        raise ValueError(
            f"Metadata sampling for mode '{resolution.requested_mode}' failed: {resolution.fallback_reason}. "
            "fallback_on_optional_error is False."
        )

    if (
        sampling_enabled
        and resolution.fallback_reason
        and strict_validation
        and resolution.requested_mode not in ("legacy", "legacy_random", "legacy_uniform_yaw")
    ):
        raise ValueError(
            f"[Sampling][{role_key}] strict_validation rejected fallback "
            f"requested={resolution.requested_mode} effective={resolution.effective_mode} "
            f"reason={resolution.fallback_reason}"
        )

    startup_log: Dict[str, Any] = {
        "role": role_key,
        "gates": {
            "training.enabled": gate["training_enabled"],
            "metadata_sampling": gate["metadata_sampling"],
            "open": gate["open"],
        },
        "requested_mode": resolution.requested_mode,
        "effective_mode": resolution.effective_mode,
        "fallback_reason": resolution.fallback_reason,
        "config_source": config_source,
        "fallback_on_optional_error": fallback_optional,
        "strict_validation": strict_validation,
        "metadata_path": str(requested_metadata_path),
        "metadata_path_absolute_configured": absolute_configured,
        "metadata_status": rt_meta.status.value if rt_meta else ("disabled" if not sampling_enabled else "unavailable"),
        "sample_count": rt_meta.sample_count if rt_meta else sample_count,
        "matched_count": rt_meta.matched_count if rt_meta else 0,
        "matched_ratio": rt_meta.matched_ratio if rt_meta else 0.0,
        "fingerprint": rt_meta.dataset_fingerprint if rt_meta else None,
        "seed": sampling_cfg.seed,
        "mode": sampling_cfg.mode.value,
    }

    if resolution.policy and hasattr(resolution.policy, "describe"):
        startup_log["policy_details"] = resolution.policy.describe()

    log_lines = [
        f"[Sampling][{role_key}]",
        (
            f"  gates: training.enabled={str(gate['training_enabled']).lower()}, "
            f"metadata_sampling={str(gate['metadata_sampling']).lower()}"
            if sampling_enabled
            else "  gates: disabled"
        ),
        f"  requested: {resolution.requested_mode}",
        f"  effective: {resolution.effective_mode}",
        f"  config source: {config_source}",
        f"  optional flags: fallback_on_optional_error={str(fallback_optional).lower()} "
        f"strict_validation={str(strict_validation).lower()}",
        f"  metadata path: {requested_metadata_path}",
    ]

    if absolute_configured:
        log_lines.append(f"  metadata path (absolute configured): {requested_metadata_path}")

    if not sampling_enabled:
        log_lines.append("  metadata: not loaded")
    elif rt_meta and rt_meta.status == FacesetMetadataStatus.LOADED:
        log_lines.append(
            f"  metadata: loaded, matched={rt_meta.matched_count}/{rt_meta.sample_count} "
            f"({rt_meta.matched_ratio * 100:.1f}%)"
        )
        log_lines.append(
            f"  trusted match: {rt_meta.matched_count}/{rt_meta.sample_count} "
            f"({rt_meta.matched_ratio * 100:.1f}%)"
        )
        if rt_meta.dataset_fingerprint:
            log_lines.append(f"  fingerprint: {rt_meta.dataset_fingerprint[:16]}...")
    elif rt_meta:
        log_lines.append(f"  metadata: {rt_meta.status.value}")
        log_lines.append(
            f"  trusted match: {rt_meta.matched_count}/{rt_meta.sample_count} "
            f"({rt_meta.matched_ratio * 100:.1f}%)"
        )
        if rt_meta.fallback_reason:
            log_lines.append(f"  optional status reason: {rt_meta.fallback_reason}")
    else:
        log_lines.append("  metadata: unavailable")

    if resolution.fallback_reason:
        log_lines.append(f"  fallback reason: {resolution.fallback_reason}")
    else:
        log_lines.append("  fallback: none")

    if sampling_cfg.seed is not None:
        log_lines.append(f"  seed: {sampling_cfg.seed}")

    io.log_info("\n".join(log_lines))

    return SamplingRuntime(
        role=role_key,
        metadata_runtime=rt_meta,
        resolution=resolution,
        startup_log=startup_log,
        sampling_config=sampling_cfg,
    )
