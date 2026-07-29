import unittest
import numpy as np

from samplelib.sampling.weights import QualityWeightResult, compute_quality_weights


class TestBatch2QualityWeights(unittest.TestCase):

    def test_smoothstep_curve_values(self):
        """测试正常 [0, 1] 质量分数的 smoothstep 权重运算结果"""
        scores = np.array([0.0, 0.25, 0.50, 0.75, 1.0], dtype=np.float32)
        valid = np.ones(5, dtype=bool)

        res = compute_quality_weights(scores, valid, quality_strength=0.5)

        self.assertEqual(len(res.warnings), 0)
        self.assertEqual(res.invalid_count, 0)
        self.assertAlmostEqual(res.sample_weights[0], 0.5)   # q=0 -> weight = 1 - 0.5 = 0.5
        self.assertAlmostEqual(res.sample_weights[2], 1.0)   # q=0.5 -> weight = 1.0
        self.assertAlmostEqual(res.sample_weights[4], 1.5)   # q=1.0 -> weight = 1 + 0.5 = 1.5

        # 校验单调递增性
        for i in range(len(scores) - 1):
            self.assertLess(res.sample_weights[i], res.sample_weights[i + 1])

    def test_strength_zero(self):
        """quality_strength = 0.0 时退化为全 1.0 中性权重"""
        scores = np.array([0.1, 0.5, 0.9], dtype=np.float32)
        valid = np.ones(3, dtype=bool)

        res = compute_quality_weights(scores, valid, quality_strength=0.0)

        self.assertTrue(np.allclose(res.sample_weights, 1.0))
        self.assertEqual(res.raw_min, 1.0)
        self.assertEqual(res.raw_max, 1.0)

    def test_invalid_and_missing_quality(self):
        """测试 quality_valid=False 及 NaN/Inf 的安全性处理"""
        scores = np.array([0.8, np.nan, np.inf, 0.2], dtype=np.float32)
        valid = np.array([True, True, True, False], dtype=bool)

        res = compute_quality_weights(scores, valid, quality_strength=0.5)

        self.assertEqual(res.invalid_count, 3)
        self.assertGreater(len(res.warnings), 0)
        # NaN, Inf 以及 valid=False 的样本均应获配中性 1.0
        self.assertAlmostEqual(res.sample_weights[1], 1.0)
        self.assertAlmostEqual(res.sample_weights[2], 1.0)
        self.assertAlmostEqual(res.sample_weights[3], 1.0)
        self.assertTrue(np.isfinite(res.sample_weights).all())

    def test_all_identical_scores(self):
        """全相同质量分数的计算"""
        scores = np.full(100, 0.5, dtype=np.float32)
        valid = np.ones(100, dtype=bool)

        res = compute_quality_weights(scores, valid)

        self.assertTrue(np.allclose(res.sample_weights, 1.0))

    def test_empty_dataset(self):
        """N = 0 空输入校验"""
        res = compute_quality_weights(np.array([], dtype=np.float32), np.array([], dtype=bool))
        self.assertEqual(len(res.sample_weights), 0)
        self.assertIn("NO_SAMPLES_PROVIDED", res.warnings)


if __name__ == "__main__":
    unittest.main()
