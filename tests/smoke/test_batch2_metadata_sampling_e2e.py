import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from samplelib import SampleLoader, SampleType
from samplelib.metadata.analyzer import FacesetAnalyzer
from samplelib.metadata.contracts import UNKNOWN_BUCKET_ID, YAW_BUCKET_NAME_TO_ID
from samplelib.metadata.loader import FacesetMetadataLoader, FacesetMetadataStatus
from samplelib.sampling.config import SamplingConfig, SamplingMode
from samplelib.sampling.policies import PoseBalancedPolicy, QualityPoseBalancedPolicy
from tests.fixtures.batch2.build_synthetic_fixture import (
    build_ordinary_fixture,
    build_packed_fixture,
)


class TestBatch2MetadataSamplingE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="dfl_e2e_test_"))
        cls.chinese_dir = cls.temp_dir / "中文姿态测试集_faceset"
        cls.ordinary_dir = cls.chinese_dir / "ordinary"
        cls.packed_dir = cls.chinese_dir / "packed"

        build_ordinary_fixture(cls.ordinary_dir)
        build_packed_fixture(cls.ordinary_dir, cls.packed_dir)

    @classmethod
    def tearDownClass(cls):
        if cls.temp_dir.exists():
            shutil.rmtree(cls.temp_dir)

    def test_e2e_ordinary_faceset_pipeline(self):
        """
        End-to-End Test: Ordinary Faceset -> Analyzer -> Sidecar JSON -> Loader -> PoseBalancedPolicy -> WeightedIndexHost
        """
        # 1. Analyzer
        analyzer = FacesetAnalyzer()
        res = analyzer.analyze(self.ordinary_dir)
        meta_path = self.ordinary_dir / "faceset_metadata.v1.json"
        res.metadata.dump_json(meta_path)
        self.assertTrue(meta_path.exists())

        # 2. Loader
        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples)

        self.assertEqual(runtime.status, FacesetMetadataStatus.LOADED)
        self.assertEqual(runtime.matched_count, len(samples))
        self.assertTrue(runtime.is_usable_for_sampling())
        self.assertTrue(np.any(runtime.pose_valid), "pose_valid must contain True values")
        self.assertTrue(np.any(runtime.yaw_bucket_ids != UNKNOWN_BUCKET_ID), "yaw_bucket_ids must contain valid IDs")

        # 3. Policy & Weights
        cfg = SamplingConfig(mode=SamplingMode.POSE_BALANCED.value, pose_balance_strength=0.8, seed=42)
        policy = PoseBalancedPolicy(cfg, runtime_metadata=runtime)
        pose_res = policy.build_weights()

        self.assertEqual(len(pose_res.sample_weights), len(samples))
        self.assertTrue(np.all(np.isfinite(pose_res.sample_weights)))
        self.assertTrue(np.all(pose_res.sample_weights > 0))

        # 4. IndexHost
        host = policy.build_index_host(samples)
        client = host.create_cli()
        draws = client.multi_get(1000)
        host.close()

        self.assertEqual(len(draws), 1000)
        self.assertTrue(np.all((np.array(draws) >= 0) & (np.array(draws) < len(samples))))

    def test_e2e_packed_faceset_pipeline(self):
        """
        End-to-End Test: Packed faceset.pak -> Analyzer -> Sidecar JSON -> Loader -> Policy -> IndexHost -> draw
        """
        # 1. Analyzer
        analyzer = FacesetAnalyzer()
        res = analyzer.analyze(self.packed_dir)
        meta_path = self.packed_dir / "faceset_metadata.v1.json"
        res.metadata.dump_json(meta_path)

        # 2. Loader
        samples = SampleLoader.load(SampleType.FACE, self.packed_dir)
        runtime = FacesetMetadataLoader.load(self.packed_dir, samples)

        self.assertEqual(runtime.status, FacesetMetadataStatus.LOADED)
        self.assertTrue(np.any(runtime.pose_valid))

        valid_ids = runtime.yaw_bucket_ids[runtime.pose_valid]
        unique_buckets = set(valid_ids)
        self.assertGreaterEqual(len(unique_buckets), 2, f"Packed dataset must have >= 2 valid yaw buckets, got {unique_buckets}")

        # 3. Policy & Non-uniform weights
        cfg = SamplingConfig(mode=SamplingMode.POSE_BALANCED.value, pose_balance_strength=0.8, uniform_mix=0.0, seed=42)
        policy = PoseBalancedPolicy(cfg, runtime_metadata=runtime)
        pose_res = policy.build_weights()

        self.assertTrue(np.all(np.isfinite(pose_res.sample_weights)))
        self.assertFalse(np.allclose(pose_res.sample_weights, 1.0), "Packed sample_weights must be non-uniform")

        from samplelib.sampling.weights import weights_to_probabilities
        probs = weights_to_probabilities(pose_res.sample_weights, uniform_mix=0.0)
        self.assertAlmostEqual(float(np.sum(probs)), 1.0, places=5)

        # 4. IndexHost & Draws
        host = policy.build_index_host(samples)
        client = host.create_cli()
        draws = client.multi_get(1000)
        host.close()

        self.assertEqual(len(draws), 1000)
        self.assertTrue(np.all((np.array(draws) >= 0) & (np.array(draws) < len(samples))))

    def _name_to_yaw_map(self, samples, runtime):
        mapping = {}
        for i, s in enumerate(samples):
            name = Path(getattr(s, "filename")).name
            if runtime.pose_valid[i]:
                mapping[name] = int(runtime.yaw_bucket_ids[i])
        return mapping

    def test_packed_and_ordinary_share_canonical_bucket_ids(self):
        """Self-contained: Analyzer both sides, 100% valid-name maps equal, order-invariant."""
        analyzer = FacesetAnalyzer()

        ord_meta = self.ordinary_dir / "faceset_metadata.v1.json"
        pak_meta = self.packed_dir / "faceset_metadata.v1.json"
        analyzer.analyze(self.ordinary_dir).metadata.dump_json(ord_meta)
        analyzer.analyze(self.packed_dir).metadata.dump_json(pak_meta)

        ord_samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        ord_runtime = FacesetMetadataLoader.load(self.ordinary_dir, ord_samples)

        pak_samples = SampleLoader.load(SampleType.FACE, self.packed_dir)
        pak_runtime = FacesetMetadataLoader.load(self.packed_dir, pak_samples)

        ord_by_name = self._name_to_yaw_map(ord_samples, ord_runtime)
        pak_by_name = self._name_to_yaw_map(pak_samples, pak_runtime)

        self.assertEqual(set(ord_by_name.keys()), set(pak_by_name.keys()))
        self.assertGreater(len(ord_by_name), 0)
        self.assertEqual(ord_by_name, pak_by_name)

        # Reversed sample order must not change name→bucket semantics.
        rev_ord_samples = list(reversed(ord_samples))
        rev_ord_runtime = FacesetMetadataLoader.load(self.ordinary_dir, rev_ord_samples)
        rev_ord_by_name = self._name_to_yaw_map(rev_ord_samples, rev_ord_runtime)
        self.assertEqual(ord_by_name, rev_ord_by_name)

        # Shuffled order (deterministic) likewise.
        rng = np.random.RandomState(123)
        order = list(range(len(ord_samples)))
        rng.shuffle(order)
        shuf_samples = [ord_samples[i] for i in order]
        shuf_runtime = FacesetMetadataLoader.load(self.ordinary_dir, shuf_samples)
        shuf_by_name = self._name_to_yaw_map(shuf_samples, shuf_runtime)
        self.assertEqual(ord_by_name, shuf_by_name)

        rev_pak_samples = list(reversed(pak_samples))
        rev_pak_runtime = FacesetMetadataLoader.load(self.packed_dir, rev_pak_samples)
        rev_pak_by_name = self._name_to_yaw_map(rev_pak_samples, rev_pak_runtime)
        self.assertEqual(pak_by_name, rev_pak_by_name)

    def test_e2e_legacy_alias_sidecar_reading(self):
        """
        Verify Loader reads legacy alias bucket names (e.g. front -> center, slight_left -> minor_left)
        """
        from samplelib.metadata.identity import build_sample_id, build_sample_key

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        meta_path = self.temp_dir / "legacy_alias_metadata.v1.json"

        s0_key = build_sample_key(getattr(samples[0], "filename"), is_packed=False, faceset_root=self.ordinary_dir)
        s0_id = build_sample_id(s0_key)
        s1_key = build_sample_key(getattr(samples[1], "filename"), is_packed=False, faceset_root=self.ordinary_dir)
        s1_id = build_sample_id(s1_key)
        s2_key = build_sample_key(getattr(samples[2], "filename"), is_packed=False, faceset_root=self.ordinary_dir)
        s2_id = build_sample_id(s2_key)

        alias_raw = {
            "schema_version": 1,
            "analyzer_version": "v1.0",
            "dataset": {"format": "ordinary", "sample_count": len(samples)},
            "samples": [
                {
                    "sample_key": s0_key,
                    "sample_id": s0_id,
                    "valid": True,
                    "pose": {"valid": True, "yaw_bucket": "front", "pitch_bucket": "center"},
                },
                {
                    "sample_key": s1_key,
                    "sample_id": s1_id,
                    "valid": True,
                    "pose": {"valid": True, "yaw_bucket": "slight_left", "pitch_bucket": "up"},
                },
                {
                    "sample_key": s2_key,
                    "sample_id": s2_id,
                    "valid": True,
                    "pose": {"valid": True, "yaw_bucket": "extreme", "pitch_bucket": "down"},
                },
            ],
        }

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(alias_raw, f)

        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples, metadata_path=meta_path)

        # "front" -> "center" (ID 3)
        self.assertEqual(runtime.yaw_bucket_ids[0], YAW_BUCKET_NAME_TO_ID["center"])
        self.assertTrue(runtime.pose_valid[0])

        # "slight_left" -> "minor_left" (ID 2)
        self.assertEqual(runtime.yaw_bucket_ids[1], YAW_BUCKET_NAME_TO_ID["minor_left"])
        self.assertTrue(runtime.pose_valid[1])

    def test_e2e_pose_balanced_sampling_effect(self):
        """
        Verify R14-02 requirements:
        1. Analyzer produces >= 2 distinct valid yaw buckets
        2. Pose-balanced sample_weights are non-uniform (not all 1s)
        3. Rare bucket per-sample weight > common bucket per-sample weight
        4. pose_balance_strength = 0 produces uniform 1.0 weights
        5. Probabilities sum to 1 and are strictly positive
        6. Empirical draw frequency fits expected_distribution within 0.08 tolerance
        """
        analyzer = FacesetAnalyzer()
        res = analyzer.analyze(self.ordinary_dir)
        meta_path = self.ordinary_dir / "faceset_metadata.v1.json"
        res.metadata.dump_json(meta_path)

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples)

        # 1. Multiple valid yaw buckets
        valid_ids = runtime.yaw_bucket_ids[runtime.pose_valid]
        unique_buckets = set(valid_ids)
        self.assertGreaterEqual(len(unique_buckets), 2, f"Expected at least 2 distinct yaw buckets, got {unique_buckets}")

        # 2. Non-uniform weights with strength=0.8, uniform_mix=0.0 to align expected_distribution
        cfg = SamplingConfig(mode=SamplingMode.POSE_BALANCED.value, pose_balance_strength=0.8, uniform_mix=0.0, seed=42)
        policy = PoseBalancedPolicy(cfg, runtime_metadata=runtime)
        pose_res = policy.build_weights()

        self.assertFalse(
            np.allclose(pose_res.sample_weights, 1.0),
            "sample_weights must be non-uniform when balance_strength > 0"
        )

        # 3. Rare bucket weight > common bucket weight
        counts = pose_res.bucket_counts
        populated_b_ids = np.where(counts > 0)[0]
        self.assertGreater(len(populated_b_ids), 1)

        sorted_b_ids = sorted(populated_b_ids, key=lambda b: counts[b])
        rare_b_id = sorted_b_ids[0]
        common_b_id = sorted_b_ids[-1]

        rare_w = pose_res.bucket_weights[rare_b_id]
        common_w = pose_res.bucket_weights[common_b_id]
        self.assertGreater(
            rare_w, common_w,
            f"Rare bucket ({rare_b_id}, count={counts[rare_b_id]}) weight ({rare_w:.3f}) should be higher than common bucket ({common_b_id}, count={counts[common_b_id]}) weight ({common_w:.3f})"
        )

        # 4. balance_strength = 0 produces uniform 1.0 weights
        cfg_zero = SamplingConfig(mode=SamplingMode.POSE_BALANCED.value, pose_balance_strength=0.0, uniform_mix=0.0, seed=42)
        policy_zero = PoseBalancedPolicy(cfg_zero, runtime_metadata=runtime)
        res_zero = policy_zero.build_weights()
        self.assertTrue(np.allclose(res_zero.sample_weights, 1.0), "strength=0 must restore uniform 1.0 weights")

        # 5. Probabilities sum to 1 and are positive
        from samplelib.sampling.weights import weights_to_probabilities
        probs = weights_to_probabilities(pose_res.sample_weights, uniform_mix=0.0)
        self.assertTrue(np.all(np.isfinite(probs)))
        self.assertTrue(np.all(probs > 0))
        self.assertAlmostEqual(float(np.sum(probs)), 1.0, places=5)

        # 6. Empirical draw distribution vs expected_distribution fitting
        host = policy.build_index_host(samples)
        client = host.create_cli()
        draw_count = 5000
        draw_indices = client.multi_get(draw_count)
        host.close()

        # Compute empirical bucket counts from draws
        empirical_b_counts = np.zeros(7, dtype=np.float64)
        for idx in draw_indices:
            b_id = runtime.yaw_bucket_ids[idx]
            if 0 <= b_id < 7:
                empirical_b_counts[b_id] += 1.0

        empirical_dist = empirical_b_counts / float(draw_count)
        expected_dist = pose_res.expected_distribution

        max_diff = float(np.max(np.abs(empirical_dist - expected_dist)))
        self.assertLess(
            max_diff, 0.08,
            f"Empirical draw distribution {empirical_dist} deviates from expected {expected_dist} by {max_diff:.4f} (> 0.08)"
        )


if __name__ == "__main__":
    unittest.main()


