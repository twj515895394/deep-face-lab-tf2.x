import unittest
import numpy as np

from samplelib.metadata.loader import FacesetMetadataStatus, RuntimeMetadata
from samplelib.sampling.config import SamplingConfig, SamplingMode
from samplelib.sampling.factory import SamplingPolicyFactory
from samplelib.sampling.policies import QualityPoseBalancedPolicy
from samplelib.sampling.weights import (
    combine_sampling_weights,
    compute_pose_weights,
    compute_quality_weights,
    weights_to_probabilities,
)


class TestBatch2CombinedWeights(unittest.TestCase):

    def test_combine_sampling_weights_basic(self):
        """测试 Pose 与 Quality 权重的乘积组合、二次剪裁与均值归一化"""
        pose_w = np.array([0.5, 1.0, 2.0], dtype=np.float32)
        quality_w = np.array([0.5, 1.0, 1.5], dtype=np.float32)

        combined = combine_sampling_weights(pose_w, quality_w, min_weight=0.5, max_weight=2.0)

        self.assertTrue(np.isfinite(combined).all())
        self.assertTrue((combined > 0).all())
        self.assertAlmostEqual(float(np.mean(combined)), 1.0, places=4)
        # 断言结果落在合理相对区间，且均值为 1.0
        self.assertTrue((combined >= 0.4).all())
        self.assertTrue((combined <= 2.0).all())


    def test_rare_pose_low_quality_preservation(self):
        """核心断言：稀缺姿态但质量较低的样本，不能被乘法组合彻底清除"""
        # 姿态：900 张正脸, 10 张稀缺侧脸
        yaw_ids = np.array([1] * 900 + [6] * 10, dtype=np.int16)
        pose_val = np.ones(910, dtype=bool)

        # 质量：正脸均 0.8，稀缺侧脸均 0.1 (低质量)
        q_scores = np.array([0.8] * 900 + [0.1] * 10, dtype=np.float32)
        q_val = np.ones(910, dtype=bool)

        pose_res = compute_pose_weights(yaw_ids, pose_val, balance_strength=0.5)
        quality_res = compute_quality_weights(q_scores, q_val, quality_strength=0.5)

        combined = combine_sampling_weights(pose_res.sample_weights, quality_res.sample_weights)

        # 侧脸样本的组合权重依然必须显著大于正脸样本的权重
        rare_sample_weight = combined[900]
        common_sample_weight = combined[0]

        self.assertGreater(rare_sample_weight, common_sample_weight)
        self.assertAlmostEqual(float(np.mean(combined)), 1.0, places=4)

    def test_weights_to_probabilities_and_uniform_mix(self):
        """测试权重转概率及 uniform exploration 混合机制"""
        weights = np.array([0.5, 1.0, 1.5, 2.0], dtype=np.float32)
        N = len(weights)
        mix = 0.10

        probs = weights_to_probabilities(weights, uniform_mix=mix)

        self.assertEqual(len(probs), N)
        self.assertAlmostEqual(float(np.sum(probs)), 1.0, places=5)

        # 断言每个样本概率至少拥有 mix * (1 / N) = 0.1 * 0.25 = 0.025 的保底分量
        min_p_floor = mix * (1.0 / N)
        for p in probs:
            self.assertGreaterEqual(p, min_p_floor - 1e-6)

    def test_quality_pose_balanced_policy(self):
        """测试 QualityPoseBalancedPolicy 类及 describe() 输出"""
        N = 100
        yaw_ids = np.array([1] * 80 + [6] * 20, dtype=np.int16)
        pose_val = np.ones(N, dtype=bool)
        q_scores = np.linspace(0.1, 0.9, N, dtype=np.float32)
        q_val = np.ones(N, dtype=bool)

        rt_meta = RuntimeMetadata(
            status=FacesetMetadataStatus.LOADED,
            sample_count=N,
            matched_count=N,
            matched_ratio=1.0,
            quality_scores=q_scores,
            yaw_bucket_ids=yaw_ids,
            pitch_bucket_ids=np.zeros(N, dtype=np.int16),
            pose_valid=pose_val,
            quality_valid=q_val,
            metadata_valid=pose_val,
        )

        cfg = SamplingConfig(
            mode=SamplingMode.QUALITY_POSE_BALANCED,
            quality_strength=0.5,
            pose_balance_strength=0.5,
            uniform_mix=0.10,
        )

        policy = QualityPoseBalancedPolicy(config=cfg, runtime_metadata=rt_meta)
        self.assertEqual(policy.mode, "quality_pose_balanced")
        policy.validate()

        probs, stats = policy.build_probabilities()
        self.assertEqual(len(probs), N)
        self.assertAlmostEqual(float(np.sum(probs)), 1.0, places=5)

        desc = policy.describe()
        self.assertEqual(desc["mode"], "quality_pose_balanced")
        self.assertIn("prob_min", desc)
        self.assertIn("prob_max", desc)
        self.assertIn("invalid_quality_count", desc)

        host = policy.build_index_host([None] * N)
        self.assertIsNotNone(host)
        host.close()

    def test_factory_resolution_with_quality_pose_balanced(self):
        """测试 SamplingPolicyFactory 决断并返回 QualityPoseBalancedPolicy"""
        N = 50
        rt_meta = RuntimeMetadata(
            status=FacesetMetadataStatus.LOADED,
            sample_count=N,
            matched_count=N,
            matched_ratio=1.0,
            quality_scores=np.ones(N, dtype=np.float32),
            yaw_bucket_ids=np.ones(N, dtype=np.int16),
            pitch_bucket_ids=np.zeros(N, dtype=np.int16),
            pose_valid=np.ones(N, dtype=bool),
            quality_valid=np.ones(N, dtype=bool),
            metadata_valid=np.ones(N, dtype=bool),
        )

        cfg = SamplingConfig(mode=SamplingMode.QUALITY_POSE_BALANCED)
        resolution = SamplingPolicyFactory.resolve(
            config=cfg,
            metadata_sampling_enabled=True,
            runtime_metadata=rt_meta,
        )

        self.assertEqual(resolution.requested_mode, "quality_pose_balanced")
        self.assertEqual(resolution.effective_mode, "quality_pose_balanced")
        self.assertIsNone(resolution.fallback_reason)
        self.assertIsInstance(resolution.policy, QualityPoseBalancedPolicy)


if __name__ == "__main__":
    unittest.main()
