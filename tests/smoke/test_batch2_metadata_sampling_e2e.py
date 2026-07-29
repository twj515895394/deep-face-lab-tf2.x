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
        End-to-End Test: Packed faceset.pak -> Analyzer -> Sidecar JSON -> Loader -> PoseBalancedPolicy
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

        # 3. Policy
        cfg = SamplingConfig(mode=SamplingMode.POSE_BALANCED.value, pose_balance_strength=0.5, seed=42)
        policy = PoseBalancedPolicy(cfg, runtime_metadata=runtime)
        pose_res = policy.build_weights()
        self.assertTrue(np.all(np.isfinite(pose_res.sample_weights)))

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

        # Create sidecar with legacy aliases
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

        # "extreme" -> unknown (-1)
        self.assertEqual(runtime.yaw_bucket_ids[2], UNKNOWN_BUCKET_ID)
        self.assertFalse(runtime.pose_valid[2])



if __name__ == "__main__":
    unittest.main()
