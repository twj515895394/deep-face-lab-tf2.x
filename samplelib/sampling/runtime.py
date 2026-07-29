from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from core.enhancements import EnhancementConfig
from core.interact import interact as io
from samplelib.SampleLoader import SampleLoader, SampleType
from samplelib.metadata.loader import FacesetMetadataLoader, FacesetMetadataStatus, RuntimeMetadata
from samplelib.sampling.config import SamplingConfig
from samplelib.sampling.factory import SamplingPolicyFactory, SamplingResolution
from samplelib.sampling.policies import SamplingPolicy


@dataclass
class SamplingRuntime:
    role: str
    metadata_runtime: Optional[RuntimeMetadata]
    resolution: SamplingResolution
    startup_log: Dict[str, Any]

    @property
    def policy(self) -> SamplingPolicy:
        return self.resolution.policy


def build_sampling_runtime(
    role: str,
    samples_path: Path,
    enhancement_config: EnhancementConfig,
    legacy_uniform_yaw: bool = False,
    base_seed: Optional[int] = None,
) -> SamplingRuntime:
    """
    Build SamplingRuntime for src or dst faceset directory, resolving metadata,
    policy, fallback reason, and printing structured startup logs.
    """
    samples_path = Path(samples_path)
    sampling_enabled = enhancement_config.is_enabled("training.metadata_sampling")
    sampling_cfg = enhancement_config.sampling_config

    if base_seed is not None and sampling_cfg.seed is None:
        role_seed_offset = 1000 if role == "src" else 2000
        derived_seed = base_seed + role_seed_offset
        sampling_cfg = SamplingConfig(
            mode=sampling_cfg.mode,
            fallback_mode=sampling_cfg.fallback_mode,
            pose_balance_strength=sampling_cfg.pose_balance_strength,
            quality_strength=sampling_cfg.quality_strength,
            uniform_mix=sampling_cfg.uniform_mix,
            min_sample_weight=sampling_cfg.min_sample_weight,
            max_sample_weight=sampling_cfg.max_sample_weight,
            min_metadata_match_ratio=sampling_cfg.min_metadata_match_ratio,
            seed=derived_seed,
            log_interval_draws=sampling_cfg.log_interval_draws,
        )

    # Path resolution
    requested_metadata_path = (
        Path(sampling_cfg.metadata_path)
        if sampling_cfg.metadata_path
        else (samples_path / "faceset_metadata.v1.json")
    )

    rt_meta: Optional[RuntimeMetadata] = None
    if sampling_enabled:
        try:
            samples = SampleLoader.load(SampleType.FACE, samples_path)
            rt_meta = FacesetMetadataLoader.load(
                samples_path=samples_path,
                samples=samples,
                metadata_path=requested_metadata_path,
                min_match_ratio=sampling_cfg.min_metadata_match_ratio,
            )
        except Exception as e:
            if not enhancement_config.fallback_on_optional_error:
                raise e
            rt_meta = RuntimeMetadata(
                status=FacesetMetadataStatus.INVALID_FILE,
                sample_count=0,
                matched_count=0,
                matched_ratio=0.0,
                quality_scores=np.array([], dtype=np.float32),
                yaw_bucket_ids=np.array([], dtype=np.int16),
                pitch_bucket_ids=np.array([], dtype=np.int16),
                pose_valid=np.array([], dtype=bool),
                quality_valid=np.array([], dtype=bool),
                metadata_valid=np.array([], dtype=bool),
                fallback_reason=f"metadata_load_exception:{str(e)}",
            )

    try:
        resolution = SamplingPolicyFactory.resolve(
            config=sampling_cfg,
            metadata_sampling_enabled=sampling_enabled,
            legacy_uniform_yaw=legacy_uniform_yaw,
            runtime_metadata=rt_meta,
        )
    except Exception as e:
        if not enhancement_config.fallback_on_optional_error:
            raise e
        resolution = SamplingPolicyFactory.resolve(
            config=sampling_cfg,
            metadata_sampling_enabled=False,
            legacy_uniform_yaw=legacy_uniform_yaw,
            runtime_metadata=rt_meta,
        )

    if (
        sampling_enabled
        and resolution.fallback_reason
        and not enhancement_config.fallback_on_optional_error
        and resolution.requested_mode not in ("legacy", "legacy_random", "legacy_uniform_yaw")
    ):
        raise ValueError(
            f"Metadata sampling for mode '{resolution.requested_mode}' failed: {resolution.fallback_reason}. "
            "fallback_on_optional_error is False."
        )

    # Build startup log dict
    startup_log = {
        "role": role,
        "requested_mode": resolution.requested_mode,
        "effective_mode": resolution.effective_mode,
        "fallback_reason": resolution.fallback_reason,
        "metadata_status": rt_meta.status.value if rt_meta else "disabled",
        "sample_count": rt_meta.sample_count if rt_meta else 0,
        "matched_count": rt_meta.matched_count if rt_meta else 0,
        "matched_ratio": rt_meta.matched_ratio if rt_meta else 0.0,
        "fingerprint": rt_meta.dataset_fingerprint if rt_meta else None,
    }

    if resolution.policy and hasattr(resolution.policy, "describe"):
        startup_log["policy_details"] = resolution.policy.describe()

    # Format & print startup log using io.log_info
    log_lines = [
        f"[Sampling][{role}]",
        f"  requested: {resolution.requested_mode}",
        f"  effective: {resolution.effective_mode}",
    ]

    if rt_meta and rt_meta.status == FacesetMetadataStatus.LOADED:
        log_lines.append(
            f"  metadata: loaded, matched={rt_meta.matched_count}/{rt_meta.sample_count} ({rt_meta.matched_ratio * 100:.1f}%)"
        )
        if rt_meta.dataset_fingerprint:
            log_lines.append(f"  fingerprint: {rt_meta.dataset_fingerprint[:16]}...")
    elif rt_meta:
        log_lines.append(f"  metadata: {rt_meta.status.value}")
    else:
        log_lines.append("  metadata: disabled (master flag off)")

    if resolution.fallback_reason:
        log_lines.append(f"  fallback reason: {resolution.fallback_reason}")
    else:
        log_lines.append("  fallback: none")

    io.log_info("\n".join(log_lines))

    return SamplingRuntime(
        role=role,
        metadata_runtime=rt_meta,
        resolution=resolution,
        startup_log=startup_log,
    )
