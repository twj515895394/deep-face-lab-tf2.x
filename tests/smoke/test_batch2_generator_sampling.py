import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from facelib import FaceType
from samplelib import SampleProcessor
from samplelib.SampleGeneratorFace import SampleGeneratorFace
from samplelib.metadata.loader import FacesetMetadataStatus, RuntimeMetadata
from samplelib.sampling.config import SamplingConfig, SamplingMode
from samplelib.sampling.policies import (
    LegacyRandomPolicy,
    LegacyUniformYawPolicy,
    PoseBalancedPolicy,
    QualityPoseBalancedPolicy,
)
from tests.fixtures.batch2.build_synthetic_fixture import build_ordinary_fixture


class TestBatch2GeneratorSampling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="dfl_generator_sampling_test_"))
        cls.ordinary_dir = cls.temp_dir / "ordinary"
        build_ordinary_fixture(cls.ordinary_dir)

        sample_count = 10
        yaw_buckets = np.array([10, 10, 10, 20, 20, 30, 40, 50, 60, 70], dtype=np.int32)
        pose_valid = np.ones(sample_count, dtype=bool)
        quality_scores = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0], dtype=np.float32)
        quality_valid = np.ones(sample_count, dtype=bool)

        cls.sample_types_base = [
            {
                "sample_type": SampleProcessor.SampleType.FACE_IMAGE,
                "channel_type": SampleProcessor.ChannelType.BGR,
                "face_type": FaceType.FULL,
                "resolution": 64,
                "warp": True,
                "transform": True,
            },
        ]

        cls.usable_meta = RuntimeMetadata(
            status=FacesetMetadataStatus.LOADED,
            sample_count=sample_count,
            matched_count=sample_count,
            matched_ratio=1.0,
            quality_scores=quality_scores,
            yaw_bucket_ids=yaw_buckets,
            pitch_bucket_ids=np.zeros(sample_count, dtype=np.int32),
            pose_valid=pose_valid,
            quality_valid=quality_valid,
            metadata_valid=np.ones(sample_count, dtype=bool),
        )

    @classmethod
    def tearDownClass(cls):
        if cls.temp_dir.exists():
            shutil.rmtree(cls.temp_dir)

    def test_generator_with_legacy_random_policy(self):
        policy = LegacyRandomPolicy(seed=42)
        gen = SampleGeneratorFace(
            samples_path=self.ordinary_dir,
            debug=True,
            batch_size=2,
            output_sample_types=self.sample_types_base,
            sampling_policy=policy,
        )
        batch = next(gen)
        self.assertIsInstance(batch, list)
        self.assertEqual(len(batch), 1)
        self.assertEqual(batch[0].shape[0], 1)

    def test_generator_with_legacy_uniform_yaw_policy(self):
        policy = LegacyUniformYawPolicy(seed=42)
        gen = SampleGeneratorFace(
            samples_path=self.ordinary_dir,
            debug=True,
            batch_size=2,
            output_sample_types=self.sample_types_base,
            sampling_policy=policy,
        )
        batch = next(gen)
        self.assertIsInstance(batch, list)
        self.assertEqual(len(batch), 1)
        self.assertEqual(batch[0].shape[0], 1)

    def test_generator_with_pose_balanced_policy(self):
        config = SamplingConfig(mode=SamplingMode.POSE_BALANCED, seed=42)
        policy = PoseBalancedPolicy(config, runtime_metadata=self.usable_meta)
        gen = SampleGeneratorFace(
            samples_path=self.ordinary_dir,
            debug=True,
            batch_size=2,
            output_sample_types=self.sample_types_base,
            sampling_policy=policy,
        )
        batch = next(gen)
        self.assertIsInstance(batch, list)
        self.assertEqual(len(batch), 1)
        self.assertEqual(batch[0].shape[0], 1)

    def test_generator_with_quality_pose_balanced_policy(self):
        config = SamplingConfig(mode=SamplingMode.QUALITY_POSE_BALANCED, seed=42)
        policy = QualityPoseBalancedPolicy(config, runtime_metadata=self.usable_meta)
        gen = SampleGeneratorFace(
            samples_path=self.ordinary_dir,
            debug=True,
            batch_size=2,
            output_sample_types=self.sample_types_base,
            sampling_policy=policy,
        )
        batch = next(gen)
        self.assertIsInstance(batch, list)
        self.assertEqual(len(batch), 1)
        self.assertEqual(batch[0].shape[0], 1)

    def test_src_dst_policy_isolation(self):
        config_src = SamplingConfig(mode=SamplingMode.POSE_BALANCED, seed=100)
        policy_src = PoseBalancedPolicy(config_src, runtime_metadata=self.usable_meta)

        config_dst = SamplingConfig(mode=SamplingMode.QUALITY_POSE_BALANCED, seed=200)
        policy_dst = QualityPoseBalancedPolicy(config_dst, runtime_metadata=self.usable_meta)

        gen_src = SampleGeneratorFace(
            samples_path=self.ordinary_dir,
            debug=True,
            batch_size=2,
            output_sample_types=self.sample_types_base,
            sampling_policy=policy_src,
            sampling_role="src",
        )
        gen_dst = SampleGeneratorFace(
            samples_path=self.ordinary_dir,
            debug=True,
            batch_size=2,
            output_sample_types=self.sample_types_base,
            sampling_policy=policy_dst,
            sampling_role="dst",
        )

        batch_src = next(gen_src)
        batch_dst = next(gen_dst)

        self.assertIsInstance(batch_src, list)
        self.assertIsInstance(batch_dst, list)
        self.assertEqual(len(batch_src), 1)
        self.assertEqual(len(batch_dst), 1)


if __name__ == "__main__":
    unittest.main()
