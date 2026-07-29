from dataclasses import dataclass
from typing import Callable, Dict, Optional

from samplelib.metadata.loader import RuntimeMetadata
from samplelib.sampling.config import SamplingConfig, SamplingMode
from samplelib.sampling.policies import (
    LegacyRandomPolicy,
    LegacyUniformYawPolicy,
    PoseBalancedPolicy,
    QualityPoseBalancedPolicy,
    SamplingPolicy,
)


@dataclass
class SamplingResolution:
    requested_mode: str
    effective_mode: str
    fallback_reason: Optional[str]
    policy: SamplingPolicy

    def describe(self) -> Dict:
        return {
            "requested_mode": self.requested_mode,
            "effective_mode": self.effective_mode,
            "fallback_reason": self.fallback_reason,
            "policy": self.policy.describe(),
        }


class SamplingPolicyFactory:
    """
    Factory resolving requested sampling modes to concrete effective SamplingPolicy instances.
    Enforces strict fallback rules and safety guarantees.
    """

    _registered_policies: Dict[SamplingMode, Callable[[SamplingConfig, RuntimeMetadata], SamplingPolicy]] = {
        SamplingMode.POSE_BALANCED: lambda config, runtime_metadata: PoseBalancedPolicy(config, runtime_metadata),
        SamplingMode.QUALITY_POSE_BALANCED: lambda config, runtime_metadata: QualityPoseBalancedPolicy(config, runtime_metadata),
    }


    @classmethod
    def register_policy(
        cls,
        mode: SamplingMode,
        factory_fn: Callable[[SamplingConfig, RuntimeMetadata], SamplingPolicy],
    ) -> None:
        """Register a new policy constructor for Ticket 07/08 extensions."""
        cls._registered_policies[mode] = factory_fn


    @classmethod
    def resolve(
        cls,
        config: SamplingConfig,
        metadata_sampling_enabled: bool,
        legacy_uniform_yaw: bool = False,
        runtime_metadata: Optional[RuntimeMetadata] = None,
        role: Optional[str] = None,
    ) -> SamplingResolution:
        # Helper to construct fallback legacy policy
        def _build_legacy_policy(mode: SamplingMode) -> SamplingPolicy:
            if mode == SamplingMode.LEGACY_UNIFORM_YAW:
                return LegacyUniformYawPolicy(seed=config.seed)
            return LegacyRandomPolicy(seed=config.seed)

        # 1. Master Flag OFF
        if not metadata_sampling_enabled:
            eff_mode = SamplingMode.LEGACY_UNIFORM_YAW if legacy_uniform_yaw else SamplingMode.LEGACY_RANDOM
            return SamplingResolution(
                requested_mode=eff_mode.value,
                effective_mode=eff_mode.value,
                fallback_reason=None,
                policy=_build_legacy_policy(eff_mode),
            )

        # 2. Master Flag ON -> Check Requested Mode
        req_mode = config.mode

        # 2a. Legacy Mode requested
        if req_mode == SamplingMode.LEGACY:
            eff_mode = SamplingMode.LEGACY_UNIFORM_YAW if legacy_uniform_yaw else SamplingMode.LEGACY_RANDOM
            return SamplingResolution(
                requested_mode="legacy",
                effective_mode=eff_mode.value,
                fallback_reason=None,
                policy=_build_legacy_policy(eff_mode),
            )

        if req_mode == SamplingMode.LEGACY_RANDOM:
            return SamplingResolution(
                requested_mode=SamplingMode.LEGACY_RANDOM.value,
                effective_mode=SamplingMode.LEGACY_RANDOM.value,
                fallback_reason=None,
                policy=_build_legacy_policy(SamplingMode.LEGACY_RANDOM),
            )

        if req_mode == SamplingMode.LEGACY_UNIFORM_YAW:
            return SamplingResolution(
                requested_mode=SamplingMode.LEGACY_UNIFORM_YAW.value,
                effective_mode=SamplingMode.LEGACY_UNIFORM_YAW.value,
                fallback_reason=None,
                policy=_build_legacy_policy(SamplingMode.LEGACY_UNIFORM_YAW),
            )

        # 2b. New Mode requested (POSE_BALANCED or QUALITY_POSE_BALANCED)
        # Check runtime metadata usability
        if runtime_metadata is None or not runtime_metadata.is_usable_for_sampling(config.min_metadata_match_ratio):
            fallback_reason = runtime_metadata.status.value if runtime_metadata else "METADATA_UNAVAILABLE"
            fb_mode = config.fallback_mode
            return SamplingResolution(
                requested_mode=req_mode.value,
                effective_mode=fb_mode.value,
                fallback_reason=fallback_reason,
                policy=_build_legacy_policy(fb_mode),
            )

        # Runtime metadata is usable -> Check if policy is registered
        if req_mode in cls._registered_policies:
            policy_inst = cls._registered_policies[req_mode](config, runtime_metadata)
            return SamplingResolution(
                requested_mode=req_mode.value,
                effective_mode=req_mode.value,
                fallback_reason=None,
                policy=policy_inst,
            )
        else:
            # Policy requested but not yet registered (Ticket 06 phase) -> Fallback safely
            fb_mode = config.fallback_mode
            return SamplingResolution(
                requested_mode=req_mode.value,
                effective_mode=fb_mode.value,
                fallback_reason="policy_not_yet_registered",
                policy=_build_legacy_policy(fb_mode),
            )
