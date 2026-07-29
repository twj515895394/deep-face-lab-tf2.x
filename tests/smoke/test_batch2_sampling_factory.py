import unittest
from typing import Any, List, Optional

from samplelib.metadata.loader import FacesetMetadataStatus, RuntimeMetadata
from samplelib.sampling.config import SamplingConfig, SamplingMode
from samplelib.sampling.factory import SamplingPolicyFactory, SamplingResolution
from samplelib.sampling.policies import LegacyRandomPolicy, LegacyUniformYawPolicy, SamplingPolicy


class DummyNewPolicy(SamplingPolicy):
    def __init__(self, mode_str: str):
        self._mode = mode_str

    @property
    def mode(self) -> str:
        return self._mode

    def build_index_host(self, samples: List[Any], role: Optional[str] = None) -> Any:
        return None


class TestBatch2SamplingFactory(unittest.TestCase):
    def setUp(self):
        # Create a usable dummy RuntimeMetadata
        self.usable_meta = RuntimeMetadata(
            status=FacesetMetadataStatus.LOADED,
            sample_count=10,
            matched_count=10,
            matched_ratio=1.0,
            quality_scores=None,
            yaw_bucket_ids=None,
            pitch_bucket_ids=None,
            pose_valid=None,
            quality_valid=None,
            metadata_valid=None,
        )

        self.unusable_meta = RuntimeMetadata(
            status=FacesetMetadataStatus.MISSING,
            sample_count=10,
            matched_count=0,
            matched_ratio=0.0,
            quality_scores=None,
            yaw_bucket_ids=None,
            pitch_bucket_ids=None,
            pose_valid=None,
            quality_valid=None,
            metadata_valid=None,
        )

    def test_decision_matrix_table(self):
        # 1. master=False, requested=any, uniform_yaw=False -> legacy_random
        cfg = SamplingConfig(mode=SamplingMode.POSE_BALANCED)
        res1 = SamplingPolicyFactory.resolve(cfg, metadata_sampling_enabled=False, legacy_uniform_yaw=False)
        self.assertEqual(res1.effective_mode, "legacy_random")
        self.assertIsInstance(res1.policy, LegacyRandomPolicy)

        # 2. master=False, requested=any, uniform_yaw=True -> legacy_uniform_yaw
        res2 = SamplingPolicyFactory.resolve(cfg, metadata_sampling_enabled=False, legacy_uniform_yaw=True)
        self.assertEqual(res2.effective_mode, "legacy_uniform_yaw")
        self.assertIsInstance(res2.policy, LegacyUniformYawPolicy)

        # 3. master=True, requested=legacy, uniform_yaw=False -> legacy_random
        cfg_leg = SamplingConfig(mode=SamplingMode.LEGACY)
        res3 = SamplingPolicyFactory.resolve(cfg_leg, metadata_sampling_enabled=True, legacy_uniform_yaw=False)
        self.assertEqual(res3.effective_mode, "legacy_random")

        # 4. master=True, requested=legacy, uniform_yaw=True -> legacy_uniform_yaw
        res4 = SamplingPolicyFactory.resolve(cfg_leg, metadata_sampling_enabled=True, legacy_uniform_yaw=True)
        self.assertEqual(res4.effective_mode, "legacy_uniform_yaw")

        # 5. master=True, requested=legacy_random -> legacy_random
        cfg_rand = SamplingConfig(mode=SamplingMode.LEGACY_RANDOM)
        res5 = SamplingPolicyFactory.resolve(cfg_rand, metadata_sampling_enabled=True, legacy_uniform_yaw=True)
        self.assertEqual(res5.effective_mode, "legacy_random")

        # 6. master=True, requested=legacy_uniform_yaw -> legacy_uniform_yaw
        cfg_yaw = SamplingConfig(mode=SamplingMode.LEGACY_UNIFORM_YAW)
        res6 = SamplingPolicyFactory.resolve(cfg_yaw, metadata_sampling_enabled=True, legacy_uniform_yaw=False)
        self.assertEqual(res6.effective_mode, "legacy_uniform_yaw")

        # 7. master=True, requested=pose_balanced, metadata=unavailable -> fallback_mode
        cfg_pose = SamplingConfig(mode=SamplingMode.POSE_BALANCED, fallback_mode=SamplingMode.LEGACY_RANDOM)
        res7 = SamplingPolicyFactory.resolve(
            cfg_pose, metadata_sampling_enabled=True, runtime_metadata=self.unusable_meta
        )
        self.assertEqual(res7.requested_mode, "pose_balanced")
        self.assertEqual(res7.effective_mode, "legacy_random")
        self.assertEqual(res7.fallback_reason, "missing")

        # 8. master=True, requested=quality_pose_balanced, metadata=usable, policy registered -> new policy
        SamplingPolicyFactory.register_policy(
            SamplingMode.QUALITY_POSE_BALANCED, lambda cfg, meta: DummyNewPolicy("quality_pose_balanced")
        )
        cfg_qpose = SamplingConfig(mode=SamplingMode.QUALITY_POSE_BALANCED)
        res8 = SamplingPolicyFactory.resolve(
            cfg_qpose, metadata_sampling_enabled=True, runtime_metadata=self.usable_meta
        )
        self.assertEqual(res8.requested_mode, "quality_pose_balanced")
        self.assertEqual(res8.effective_mode, "quality_pose_balanced")
        self.assertIsNone(res8.fallback_reason)
        self.assertIsInstance(res8.policy, DummyNewPolicy)


if __name__ == "__main__":
    unittest.main()
