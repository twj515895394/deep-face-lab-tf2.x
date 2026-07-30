"""Ticket 16: real SubprocessGenerator (debug=False) sampling path tests."""

from __future__ import annotations

import multiprocessing
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
    PoseBalancedPolicy,
)
from tests.fixtures.batch2.build_synthetic_fixture import (
    build_ordinary_fixture,
    build_packed_fixture,
)


class TestBatch2GeneratorSamplingSpawn(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="dfl_generator_spawn_"))
        cls.ordinary_dir = cls.temp_dir / "ordinary"
        cls.packed_dir = cls.temp_dir / "packed"
        build_ordinary_fixture(cls.ordinary_dir)
        cls.packed_file = build_packed_fixture(cls.ordinary_dir, cls.packed_dir)

        sample_count = 10
        yaw_buckets = np.array([10, 10, 10, 20, 20, 30, 40, 50, 60, 70], dtype=np.int32)
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
            quality_scores=np.linspace(0.1, 1.0, sample_count, dtype=np.float32),
            yaw_bucket_ids=yaw_buckets,
            pitch_bucket_ids=np.zeros(sample_count, dtype=np.int32),
            pose_valid=np.ones(sample_count, dtype=bool),
            quality_valid=np.ones(sample_count, dtype=bool),
            metadata_valid=np.ones(sample_count, dtype=bool),
        )

    @classmethod
    def tearDownClass(cls):
        if cls.temp_dir.exists():
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _assert_batches(self, gen, batch_size, n_batches=3):
        for _ in range(n_batches):
            batch = next(gen)
            self.assertIsInstance(batch, list)
            self.assertGreaterEqual(len(batch), 1)
            arr = batch[0]
            self.assertEqual(arr.shape[0], batch_size)
            self.assertTrue(np.issubdtype(arr.dtype, np.floating) or arr.dtype == np.uint8 or arr.dtype == np.float32 or arr.dtype == np.float16)

    def _capture_worker_handles(self, gen):
        """Capture Process handles before finalize so tests do not trust g.p=None."""
        handles = []
        for g in getattr(gen, "generators", None) or []:
            p = getattr(g, "p", None)
            if p is not None:
                handles.append(p)
        return handles

    def _assert_workers_reaped(self, handles, children_before):
        for p in handles:
            self.assertFalse(p.is_alive(), f"worker still alive pid={getattr(p, 'pid', None)}")
            self.assertIsNotNone(p.exitcode)
        # No new residual children relative to the pre-start baseline.
        residual = [
            c for c in multiprocessing.active_children()
            if c not in children_before and c.is_alive()
        ]
        self.assertEqual(
            residual,
            [],
            f"unexpected residual children: {[getattr(c, 'pid', None) for c in residual]}",
        )

    def test_debug_false_ordinary_pose_balanced(self):
        config = SamplingConfig(mode=SamplingMode.POSE_BALANCED, seed=42)
        policy = PoseBalancedPolicy(config, runtime_metadata=self.usable_meta)
        batch_size = 2
        children_before = set(multiprocessing.active_children())
        gen = SampleGeneratorFace(
            samples_path=self.ordinary_dir,
            debug=False,
            batch_size=batch_size,
            generators_count=2,
            output_sample_types=self.sample_types_base,
            sampling_policy=policy,
        )
        host = None
        worker_handles = []
        try:
            self.assertTrue(gen.is_initialized())
            self.assertIsNotNone(gen.index_host)
            host = gen.index_host
            self.assertEqual(len(gen.generators), 2)
            for g in gen.generators:
                self.assertIsNotNone(getattr(g, "p", None))
                self.assertTrue(g.p.is_alive())

            self._assert_batches(gen, batch_size=batch_size, n_batches=4)

            stats_before_close = host.snapshot_stats()
            self.assertGreaterEqual(stats_before_close["total_draws"], batch_size)
            worker_handles = self._capture_worker_handles(gen)
            self.assertEqual(len(worker_handles), 2)
        finally:
            gen.finalize()

        self._assert_workers_reaped(worker_handles, children_before)
        for g in gen.generators:
            self.assertIsNone(getattr(g, "p", None))
            self.assertTrue(getattr(g, "_closed", False))
        if host is not None:
            self.assertFalse(host.thread.is_alive())

        # finalize is idempotent after successful reaping
        gen.finalize()

    def test_debug_false_packed_pose_balanced(self):
        config = SamplingConfig(mode=SamplingMode.POSE_BALANCED, seed=7)
        policy = PoseBalancedPolicy(config, runtime_metadata=self.usable_meta)
        batch_size = 2
        children_before = set(multiprocessing.active_children())
        gen = SampleGeneratorFace(
            samples_path=self.packed_dir,
            debug=False,
            batch_size=batch_size,
            generators_count=2,
            output_sample_types=self.sample_types_base,
            sampling_policy=policy,
        )
        host = None
        worker_handles = []
        try:
            self.assertTrue(gen.is_initialized())
            host = gen.index_host
            self._assert_batches(gen, batch_size=batch_size, n_batches=3)
            worker_handles = self._capture_worker_handles(gen)
        finally:
            gen.finalize()

        self._assert_workers_reaped(worker_handles, children_before)
        for g in gen.generators:
            self.assertIsNone(getattr(g, "p", None))
        if host is not None and hasattr(host, "thread"):
            self.assertFalse(host.thread.is_alive())

    def test_debug_false_legacy_random_regression(self):
        policy = LegacyRandomPolicy(seed=3)
        batch_size = 2
        children_before = set(multiprocessing.active_children())
        gen = SampleGeneratorFace(
            samples_path=self.ordinary_dir,
            debug=False,
            batch_size=batch_size,
            generators_count=2,
            output_sample_types=self.sample_types_base,
            sampling_policy=policy,
        )
        worker_handles = []
        try:
            self._assert_batches(gen, batch_size=batch_size, n_batches=2)
            worker_handles = self._capture_worker_handles(gen)
        finally:
            gen.finalize()
        self._assert_workers_reaped(worker_handles, children_before)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    unittest.main()
