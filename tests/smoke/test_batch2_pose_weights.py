import unittest
import numpy as np

from samplelib.metadata.loader import FacesetMetadataStatus, RuntimeMetadata
from samplelib.sampling.config import SamplingConfig, SamplingMode
from samplelib.sampling.factory import SamplingPolicyFactory
from samplelib.sampling.policies import PoseBalancedPolicy
from samplelib.sampling.weights import PoseWeightResult, compute_pose_weights


class TestBatch2PoseWeights(unittest.TestCase):

    def _build_dataset_from_counts(self, counts, unknown_count=0, invalid_count=0):
        """
        Helper to construct synthetic yaw_bucket_ids and pose_valid arrays.
        counts: list of counts for buckets 0..6
        """
        yaw_list = []
        valid_list = []

        for b_id, count in enumerate(counts):
            yaw_list.extend([b_id] * count)
            valid_list.extend([True] * count)

        for _ in range(unknown_count):
            yaw_list.append(-1)
            valid_list.append(True)

        for _ in range(invalid_count):
            yaw_list.append(1)  # valid bucket ID but pose_valid=False
            valid_list.append(False)

        return np.array(yaw_list, dtype=np.int16), np.array(valid_list, dtype=bool)

    def test_array_a_balanced(self):
        """A: [10,10,10,10,10,10,10] 完全平衡姿态分布"""
        yaw_ids, valid = self._build_dataset_from_counts([10, 10, 10, 10, 10, 10, 10])
        res = compute_pose_weights(yaw_ids, valid, balance_strength=0.5)

        self.assertEqual(len(res.warnings), 0)
        self.assertTrue(np.allclose(res.bucket_weights, 1.0))
        self.assertTrue(np.allclose(res.sample_weights, 1.0))
        self.assertAlmostEqual(float(np.mean(res.sample_weights)), 1.0, places=5)
        self.assertTrue((res.sample_weights > 0).all())
        self.assertTrue(np.isfinite(res.sample_weights).all())

    def test_array_b_strong_imbalance(self):
        """B: [900,20,20,15,15,15,15] 强失衡姿态分布"""
        yaw_ids, valid = self._build_dataset_from_counts([900, 20, 20, 15, 15, 15, 15])
        res = compute_pose_weights(yaw_ids, valid, balance_strength=0.5, min_bucket_weight=0.5, max_bucket_weight=2.0)

        self.assertEqual(len(res.warnings), 0)
        # 900 样本的 bucket (b=0) 计算出的权重应低于 1.0 且被剪裁到 0.5
        self.assertAlmostEqual(res.bucket_weights[0], 0.5)
        # 15 样本的 bucket 权重应大于 900 样本 bucket 的权重
        self.assertGreater(res.bucket_weights[3], res.bucket_weights[0])
        self.assertTrue(np.isfinite(res.sample_weights).all())
        self.assertTrue((res.sample_weights > 0).all())
        self.assertAlmostEqual(float(np.mean(res.sample_weights)), 1.0, places=5)


    def test_array_c_single_bucket(self):
        """C: [100,0,0,0,0,0,0] 只有单非空 Bucket"""
        yaw_ids, valid = self._build_dataset_from_counts([100, 0, 0, 0, 0, 0, 0])
        res = compute_pose_weights(yaw_ids, valid, balance_strength=0.5)

        self.assertEqual(len(res.warnings), 0)
        self.assertTrue(np.allclose(res.sample_weights, 1.0))
        self.assertAlmostEqual(float(np.mean(res.sample_weights)), 1.0, places=5)

    def test_array_d_extreme_scarcity(self):
        """D: [0,0,0,0,0,0,1] 极稀缺单张样本"""
        yaw_ids, valid = self._build_dataset_from_counts([10, 10, 10, 10, 10, 10, 1])
        res = compute_pose_weights(yaw_ids, valid, balance_strength=0.5, max_bucket_weight=2.0)

        # 极稀缺 bucket 6 应该被上限限制为 2.0
        self.assertAlmostEqual(res.bucket_weights[6], 2.0)
        self.assertTrue(np.isfinite(res.sample_weights).all())
        self.assertTrue((res.sample_weights > 0).all())

    def test_array_e_all_unknown(self):
        """E: 全 Unknown 或 Invalid 姿态数据"""
        yaw_ids, valid = self._build_dataset_from_counts([0] * 7, unknown_count=50, invalid_count=20)
        res = compute_pose_weights(yaw_ids, valid)

        self.assertIn("ALL_SAMPLES_UNKNOWN_OR_INVALID", res.warnings)
        self.assertTrue(np.allclose(res.sample_weights, 1.0))

    def test_array_f_partial_invalid_and_unknown(self):
        """F: 部分 Invalid + Unknown 混合数据"""
        yaw_ids, valid = self._build_dataset_from_counts([50, 10, 10, 0, 0, 0, 0], unknown_count=15, invalid_count=5)
        res = compute_pose_weights(yaw_ids, valid, unknown_weight=0.75)

        self.assertTrue(np.isfinite(res.sample_weights).all())
        self.assertTrue((res.sample_weights > 0).all())
        self.assertAlmostEqual(float(np.mean(res.sample_weights)), 1.0, places=5)

    def test_balance_strength_zero(self):
        """balance_strength = 0.0 时退化为等权"""
        yaw_ids, valid = self._build_dataset_from_counts([900, 20, 20, 15, 15, 15, 15])
        res = compute_pose_weights(yaw_ids, valid, balance_strength=0.0)

        self.assertTrue(np.allclose(res.bucket_weights, 1.0))
        self.assertTrue(np.allclose(res.sample_weights, 1.0))

    def test_empty_dataset(self):
        """N = 0 极端边界防御"""
        res = compute_pose_weights(np.array([], dtype=np.int16), np.array([], dtype=bool))
        self.assertEqual(len(res.sample_weights), 0)
        self.assertIn("NO_SAMPLES_PROVIDED", res.warnings)

    def test_pose_balanced_policy_class(self):
        """测试 PoseBalancedPolicy 接口契约"""
        yaw_ids, valid = self._build_dataset_from_counts([100, 20, 20, 10, 10, 10, 10])
        N = len(yaw_ids)

        rt_meta = RuntimeMetadata(
            status=FacesetMetadataStatus.LOADED,
            sample_count=N,
            matched_count=N,
            matched_ratio=1.0,
            quality_scores=np.ones(N, dtype=np.float32),
            yaw_bucket_ids=yaw_ids,
            pitch_bucket_ids=np.zeros(N, dtype=np.int16),
            pose_valid=valid,
            quality_valid=valid,
            metadata_valid=valid,
        )

        cfg = SamplingConfig(mode=SamplingMode.POSE_BALANCED, pose_balance_strength=0.5)
        policy = PoseBalancedPolicy(config=cfg, runtime_metadata=rt_meta)

        self.assertEqual(policy.mode, "pose_balanced")
        policy.validate()

        res = policy.build_weights()
        self.assertIsInstance(res, PoseWeightResult)
        self.assertEqual(len(res.sample_weights), N)

        desc = policy.describe()
        self.assertEqual(desc["mode"], "pose_balanced")
        self.assertIn("bucket_counts", desc)
        self.assertIn("expected_distribution", desc)

        host = policy.build_index_host([None] * N)
        self.assertIsNotNone(host)
        host.close()

    def test_factory_resolution_with_pose_balanced(self):
        """测试 SamplingPolicyFactory 决断并返回 PoseBalancedPolicy"""
        yaw_ids, valid = self._build_dataset_from_counts([50, 50, 50, 50, 50, 50, 50])
        N = len(yaw_ids)

        rt_meta = RuntimeMetadata(
            status=FacesetMetadataStatus.LOADED,
            sample_count=N,
            matched_count=N,
            matched_ratio=1.0,
            quality_scores=np.ones(N, dtype=np.float32),
            yaw_bucket_ids=yaw_ids,
            pitch_bucket_ids=np.zeros(N, dtype=np.int16),
            pose_valid=valid,
            quality_valid=valid,
            metadata_valid=valid,
        )

        cfg = SamplingConfig(mode=SamplingMode.POSE_BALANCED)
        resolution = SamplingPolicyFactory.resolve(
            config=cfg,
            metadata_sampling_enabled=True,
            runtime_metadata=rt_meta,
        )

        self.assertEqual(resolution.requested_mode, "pose_balanced")
        self.assertEqual(resolution.effective_mode, "pose_balanced")
        self.assertIsNone(resolution.fallback_reason)
        self.assertIsInstance(resolution.policy, PoseBalancedPolicy)

    def test_sampling_distribution_simulation(self):
        """使用 Monte Carlo 大样本随机抽样模拟验证理论期望与实际抽样频率匹配"""
        yaw_ids, valid = self._build_dataset_from_counts([1000, 100, 100, 50, 50, 50, 50])
        res = compute_pose_weights(yaw_ids, valid, balance_strength=0.5)

        p = res.sample_weights / np.sum(res.sample_weights)

        rng = np.random.default_rng(42)
        sim_draws = 50000
        chosen_indices = rng.choice(len(yaw_ids), size=sim_draws, p=p)

        # 统计抽到的 bucket 概率
        chosen_yaws = yaw_ids[chosen_indices]
        sim_counts = np.bincount(chosen_yaws, minlength=7)
        sim_distribution = sim_counts / float(sim_draws)

        # 验证模拟分布与 expected_distribution 偏差小于 1.5%
        for b in range(7):
            diff = abs(sim_distribution[b] - res.expected_distribution[b])
            self.assertLess(diff, 0.015, f"Bucket {b} simulation frequency deviates from expected distribution.")


if __name__ == "__main__":
    unittest.main()
