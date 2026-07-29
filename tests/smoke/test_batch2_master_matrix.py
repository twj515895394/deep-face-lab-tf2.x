import compileall
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from core.enhancements import EnhancementConfig
from samplelib.metadata.identity import build_sample_id, build_sample_key
from samplelib.metadata.loader import FacesetMetadataLoader, FacesetMetadataStatus
from samplelib.metadata.schema import SCHEMA_VERSION_CURRENT, FacesetMetadataV1
from samplelib.sampling.config import SamplingConfig, SamplingMode
from samplelib.sampling.factory import SamplingPolicyFactory
from samplelib.sampling.runtime import build_sampling_runtime
from samplelib.sampling.weighted_index_host import WeightedCycleSampler, WeightedIndexHost, WeightedIndexHostConfig
from mainscripts import FacesetAnalyzer
from tests.fixtures.batch2.build_synthetic_fixture import build_ordinary_fixture, build_packed_fixture


class TestBatch2MasterMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="dfl_master_matrix_test_"))
        cls.ordinary_dir = cls.temp_dir / "ordinary"
        cls.packed_dir = cls.temp_dir / "packed"
        build_ordinary_fixture(cls.ordinary_dir)
        build_packed_fixture(cls.ordinary_dir, cls.packed_dir)
        FacesetAnalyzer.main(cls.ordinary_dir)
        FacesetAnalyzer.main(cls.packed_dir)

    @classmethod
    def tearDownClass(cls):
        if cls.temp_dir.exists():
            shutil.rmtree(cls.temp_dir)

    def test_layer_0_compilation(self):
        """Layer 0: Verify Python compilation of all Batch 2 modules."""
        target_dirs = [
            Path("samplelib/metadata"),
            Path("samplelib/sampling"),
        ]
        for tdir in target_dirs:
            compiled = compileall.compile_dir(tdir, quiet=1)
            self.assertTrue(compiled, f"Compilation failed for {tdir}")

    def test_layer_1_pure_functions(self):
        """Layer 1: Identity, Schema, Config, Factory resolution."""
        key = build_sample_key("00001.jpg", 1024, 0)
        self.assertIn("00001.jpg", key)

        schema = FacesetMetadataV1(
            schema_version=SCHEMA_VERSION_CURRENT,
            dataset={"fingerprint": "a1b2c3d4e5f67890a1b2c3d4e5f67890"},
            samples=[]
        )
        dict_repr = schema.to_dict()
        self.assertEqual(dict_repr["schema_version"], SCHEMA_VERSION_CURRENT)

        config = SamplingConfig(mode=SamplingMode.QUALITY_POSE_BALANCED)
        self.assertEqual(config.mode, SamplingMode.QUALITY_POSE_BALANCED)

    def test_layer_2_analyzer_and_store(self):
        """Layer 2: Check presence of metadata sidecar after build."""
        ordinary_meta = self.ordinary_dir / "faceset_metadata.v1.json"
        packed_meta = self.packed_dir / "faceset_metadata.v1.json"
        self.assertTrue(ordinary_meta.exists())
        self.assertTrue(packed_meta.exists())

    def test_layer_3_loader(self):
        """Layer 3: Loader RuntimeMetadata loading and usable_for_sampling."""
        from samplelib.SampleLoader import SampleLoader, SampleType
        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        rt_meta = FacesetMetadataLoader.load(
            samples_path=self.ordinary_dir,
            samples=samples,
            metadata_path=self.ordinary_dir / "faceset_metadata.v1.json"
        )
        self.assertTrue(rt_meta.is_usable_for_sampling())
        self.assertEqual(rt_meta.status, FacesetMetadataStatus.LOADED)

    def test_layer_4_weighted_sampler_and_host(self):
        """Layer 4: Cycle sampler determinism and Host server thread."""
        weights = np.array([1.0, 3.0, 2.0], dtype=np.float64)
        cfg_seed = WeightedIndexHostConfig(seed=42)
        sampler = WeightedCycleSampler(weights, config=cfg_seed)
        indices_1 = sampler.draw(100)
        
        sampler2 = WeightedCycleSampler(weights, config=cfg_seed)
        indices_2 = sampler2.draw(100)
        np.testing.assert_array_equal(indices_1, indices_2)

        # Check distribution tolerance (Chi-Square/relative error within 5%)
        large_batch = sampler.draw(60000)
        counts = np.bincount(large_batch, minlength=3)
        actual_freq = counts / 60000.0
        expected_freq = weights / np.sum(weights)
        max_err = np.max(np.abs(actual_freq - expected_freq))
        self.assertLess(max_err, 0.05)

        # Check Host lifecycle
        host = WeightedIndexHost(weights, config=cfg_seed)
        client = host.create_cli()
        drawn = client.multi_get(10)
        self.assertEqual(len(drawn), 10)
        host.close()

    def test_layer_5_generator_and_runtime(self):
        """Layer 5: Build sampling runtime for src and dst."""
        cfg = EnhancementConfig.from_mapping({
            "training": {"enabled": True, "metadata_sampling": True},
            "sampling": {"mode": "quality_pose_balanced"}
        })
        src_rt = build_sampling_runtime("src", self.ordinary_dir, cfg, base_seed=42)
        dst_rt = build_sampling_runtime("dst", self.packed_dir, cfg, base_seed=42)

        self.assertEqual(src_rt.role, "src")
        self.assertEqual(dst_rt.role, "dst")
        self.assertEqual(src_rt.resolution.effective_mode, "quality_pose_balanced")
        self.assertEqual(dst_rt.resolution.effective_mode, "quality_pose_balanced")


if __name__ == "__main__":
    unittest.main()
