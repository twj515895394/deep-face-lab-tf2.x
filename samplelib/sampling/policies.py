from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from core import mplib
from samplelib.metadata.loader import RuntimeMetadata
from samplelib.sampling.config import SamplingConfig, SamplingMode
from samplelib.sampling.weights import (
    PoseWeightResult,
    QualityWeightResult,
    combine_sampling_weights,
    compute_pose_weights,
    compute_quality_weights,
    weights_to_probabilities,
)


from samplelib.sampling.weighted_index_host import WeightedIndexHost, WeightedIndexHostConfig


class SamplingPolicy(ABC):
    """
    Abstract base class for all faceset sampling policies.
    """

    @property
    @abstractmethod
    def mode(self) -> str:
        pass

    def validate(self) -> None:
        """Validate internal policy state prior to index host construction."""
        pass

    @abstractmethod
    def build_index_host(self, samples: List[Any], role: Optional[str] = None) -> Any:
        """Construct IndexHost or Index2DHost compatible multiprocess index server."""
        pass

    def describe(self) -> Dict[str, Any]:
        return {"mode": self.mode}


class LegacyRandomPolicy(SamplingPolicy):
    """
    Legacy 1D random uniform shuffle index host adapter.
    """

    def __init__(self, seed: Optional[int] = None):
        self.seed = seed

    @property
    def mode(self) -> str:
        return SamplingMode.LEGACY_RANDOM.value

    def build_index_host(self, samples: List[Any], role: Optional[str] = None) -> Any:
        N = len(samples)
        if N == 0:
            raise ValueError("No training data provided.")
        return mplib.IndexHost(N, rnd_seed=self.seed)


class LegacyUniformYawPolicy(SamplingPolicy):
    """
    Legacy 128-bucket yaw distribution index host adapter.
    Preserves exact historical 2DFAN yaw range [-1.2, 1.2] linear space contract.
    """

    def __init__(self, seed: Optional[int] = None):
        self.seed = seed

    @property
    def mode(self) -> str:
        return SamplingMode.LEGACY_UNIFORM_YAW.value

    def build_index_host(self, samples: List[Any], role: Optional[str] = None) -> Any:
        N = len(samples)
        if N == 0:
            raise ValueError("No training data provided.")

        samples_pyr = [(idx, sample.get_pitch_yaw_roll()) for idx, sample in enumerate(samples)]
        grads = 128
        grads_space = np.linspace(-1.2, 1.2, grads)

        yaws_sample_list = [None] * grads
        for g in range(grads):
            yaw = grads_space[g]
            next_yaw = grads_space[g + 1] if g < grads - 1 else yaw

            yaw_samples = []
            for idx, pyr in samples_pyr:
                s_yaw = -pyr[1]
                if (g == 0 and s_yaw < next_yaw) or \
                   (g < grads - 1 and s_yaw >= yaw and s_yaw < next_yaw) or \
                   (g == grads - 1 and s_yaw >= yaw):
                    yaw_samples.append(idx)
            if len(yaw_samples) > 0:
                yaws_sample_list[g] = yaw_samples

        yaws_sample_list = [y for y in yaws_sample_list if y is not None]
        return mplib.Index2DHost(yaws_sample_list)


class PoseBalancedPolicy(SamplingPolicy):
    """
    Conservative, interpretable pose-balanced sampling policy.
    Uses discrete Yaw Bucket counts to weight rare head poses.
    """

    def __init__(self, config: SamplingConfig, runtime_metadata: Optional[RuntimeMetadata] = None):
        self.config = config
        self.runtime_metadata = runtime_metadata

    @property
    def mode(self) -> str:
        return SamplingMode.POSE_BALANCED.value

    def validate(self) -> None:
        if self.runtime_metadata is None or not self.runtime_metadata.is_usable_for_sampling():
            reason = self.runtime_metadata.fallback_reason if self.runtime_metadata else "MISSING_RUNTIME_METADATA"
            raise ValueError(f"Runtime metadata is not usable for pose balanced sampling: {reason}")

    def build_weights(self) -> PoseWeightResult:
        self.validate()

        return compute_pose_weights(
            yaw_bucket_ids=self.runtime_metadata.yaw_bucket_ids,
            pose_valid=self.runtime_metadata.pose_valid,
            balance_strength=self.config.pose_balance_strength,
            unknown_weight=0.75,
            min_bucket_weight=self.config.min_sample_weight,
            max_bucket_weight=self.config.max_sample_weight,
        )

    def build_index_host(self, samples: List[Any], role: Optional[str] = None) -> Any:
        self.validate()
        pose_res = self.build_weights()
        probs = weights_to_probabilities(
            weights=pose_res.sample_weights,
            uniform_mix=self.config.uniform_mix,
        )
        host_config = WeightedIndexHostConfig(
            seed=self.config.seed,
            cycle_size=getattr(self.config, "cycle_size", None),
        )
        bucket_ids = self.runtime_metadata.yaw_bucket_ids if self.runtime_metadata else None
        return WeightedIndexHost(
            probabilities=probs,
            config=host_config,
            bucket_ids=bucket_ids,
        )

    def describe(self) -> Dict[str, Any]:
        info: Dict[str, Any] = {"mode": self.mode}
        if self.runtime_metadata and self.runtime_metadata.is_usable_for_sampling():
            try:
                res = self.build_weights()
                info.update({
                    "pose_balance_strength": self.config.pose_balance_strength,
                    "min_sample_weight": self.config.min_sample_weight,
                    "max_sample_weight": self.config.max_sample_weight,
                    "bucket_counts": res.bucket_counts.tolist(),
                    "bucket_weights": res.bucket_weights.tolist(),
                    "expected_distribution": res.expected_distribution.tolist(),
                    "warnings": res.warnings,
                })
            except Exception as e:
                info["error"] = str(e)
        else:
            info["status"] = "UNUSABLE_METADATA"
        return info


class QualityPoseBalancedPolicy(SamplingPolicy):
    """
    Combined pose-balanced and quality-aware sampling policy.
    """

    def __init__(self, config: SamplingConfig, runtime_metadata: Optional[RuntimeMetadata] = None):
        self.config = config
        self.runtime_metadata = runtime_metadata

    @property
    def mode(self) -> str:
        return SamplingMode.QUALITY_POSE_BALANCED.value

    def validate(self) -> None:
        if self.runtime_metadata is None or not self.runtime_metadata.is_usable_for_sampling():
            reason = self.runtime_metadata.fallback_reason if self.runtime_metadata else "MISSING_RUNTIME_METADATA"
            raise ValueError(f"Runtime metadata is not usable for quality-pose balanced sampling: {reason}")

    def build_probabilities(self) -> Tuple[np.ndarray, Dict[str, Any]]:
        self.validate()

        pose_res = compute_pose_weights(
            yaw_bucket_ids=self.runtime_metadata.yaw_bucket_ids,
            pose_valid=self.runtime_metadata.pose_valid,
            balance_strength=self.config.pose_balance_strength,
            unknown_weight=0.75,
            min_bucket_weight=self.config.min_sample_weight,
            max_bucket_weight=self.config.max_sample_weight,
        )

        quality_res = compute_quality_weights(
            quality_scores=self.runtime_metadata.quality_scores,
            quality_valid=self.runtime_metadata.quality_valid,
            quality_strength=self.config.quality_strength,
        )

        combined_w = combine_sampling_weights(
            pose_weights=pose_res.sample_weights,
            quality_weights=quality_res.sample_weights,
            min_weight=self.config.min_sample_weight,
            max_weight=self.config.max_sample_weight,
        )

        probs = weights_to_probabilities(
            weights=combined_w,
            uniform_mix=self.config.uniform_mix,
        )

        stats = {
            "pose_res": pose_res,
            "quality_res": quality_res,
            "combined_weights": combined_w,
            "probabilities": probs,
        }

        return probs, stats

    def build_index_host(self, samples: List[Any], role: Optional[str] = None) -> Any:
        self.validate()
        probs, _ = self.build_probabilities()
        host_config = WeightedIndexHostConfig(
            seed=self.config.seed,
            cycle_size=getattr(self.config, "cycle_size", None),
        )
        bucket_ids = self.runtime_metadata.yaw_bucket_ids if self.runtime_metadata else None
        quality_quantiles = (
            getattr(self.runtime_metadata, "quality_quantiles", None) if self.runtime_metadata else None
        )
        return WeightedIndexHost(
            probabilities=probs,
            config=host_config,
            bucket_ids=bucket_ids,
            quality_quantiles=quality_quantiles,
        )

    def describe(self) -> Dict[str, Any]:
        info: Dict[str, Any] = {"mode": self.mode}
        if self.runtime_metadata and self.runtime_metadata.is_usable_for_sampling():
            try:
                probs, stats = self.build_probabilities()
                pose_res: PoseWeightResult = stats["pose_res"]
                quality_res: QualityWeightResult = stats["quality_res"]
                combined_w: np.ndarray = stats["combined_weights"]

                info.update({
                    "quality_strength": self.config.quality_strength,
                    "pose_balance_strength": self.config.pose_balance_strength,
                    "uniform_mix": self.config.uniform_mix,
                    "min_sample_weight": self.config.min_sample_weight,
                    "max_sample_weight": self.config.max_sample_weight,
                    "weight_min": float(np.min(combined_w)),
                    "weight_mean": float(np.mean(combined_w)),
                    "weight_max": float(np.max(combined_w)),
                    "prob_min": float(np.min(probs)),
                    "prob_max": float(np.max(probs)),
                    "invalid_quality_count": quality_res.invalid_count,
                    "bucket_counts": pose_res.bucket_counts.tolist(),
                    "bucket_weights": pose_res.bucket_weights.tolist(),
                    "expected_pose_distribution": pose_res.expected_distribution.tolist(),
                    "warnings": pose_res.warnings + quality_res.warnings,
                })
            except Exception as e:
                info["error"] = str(e)
        else:
            info["status"] = "UNUSABLE_METADATA"
        return info


