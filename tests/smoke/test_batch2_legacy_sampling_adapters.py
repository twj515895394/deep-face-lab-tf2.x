import shutil
import tempfile
import unittest
from pathlib import Path

from core import mplib
from samplelib.sampling.policies import LegacyRandomPolicy, LegacyUniformYawPolicy
from tests.fixtures.batch2.build_synthetic_fixture import build_ordinary_fixture


class TestBatch2LegacySamplingAdapters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="dfl_legacy_adapters_test_"))
        cls.ordinary_dir = cls.temp_dir / "ordinary"
        build_ordinary_fixture(cls.ordinary_dir)

    @classmethod
    def tearDownClass(cls):
        if cls.temp_dir.exists():
            shutil.rmtree(cls.temp_dir)

    def test_legacy_random_policy(self):
        from samplelib import SampleLoader, SampleType

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        policy = LegacyRandomPolicy(seed=42)

        self.assertEqual(policy.mode, "legacy_random")
        self.assertEqual(policy.describe(), {"mode": "legacy_random"})

        index_host = policy.build_index_host(samples)
        try:
            self.assertIsInstance(index_host, mplib.IndexHost)

            cli = index_host.create_cli()
            fetched = cli.multi_get(5)
            self.assertEqual(len(fetched), 5)
            for idx in fetched:
                self.assertTrue(0 <= idx < len(samples))
        finally:
            index_host.close()
            self.assertFalse(index_host.thread.is_alive())

    def test_legacy_uniform_yaw_policy(self):
        from samplelib import SampleLoader, SampleType

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        policy = LegacyUniformYawPolicy()

        self.assertEqual(policy.mode, "legacy_uniform_yaw")

        index_host = policy.build_index_host(samples)
        try:
            self.assertIsInstance(index_host, mplib.Index2DHost)

            cli = index_host.create_cli()
            fetched = cli.multi_get(5)
            self.assertEqual(len(fetched), 5)
            for idx in fetched:
                self.assertTrue(0 <= idx < len(samples))
        finally:
            index_host.close()
            self.assertFalse(index_host.thread.is_alive())

    def test_empty_samples_raises_value_error(self):
        policy_rand = LegacyRandomPolicy()
        with self.assertRaises(ValueError):
            policy_rand.build_index_host([])

        policy_yaw = LegacyUniformYawPolicy()
        with self.assertRaises(ValueError):
            policy_yaw.build_index_host([])


if __name__ == "__main__":
    unittest.main()
