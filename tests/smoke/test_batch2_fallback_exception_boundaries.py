"""Ticket 20: narrow optional Metadata fallback; core errors must propagate."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.enhancements import EnhancementConfig
from samplelib.sampling.runtime import build_sampling_runtime
from tests.fixtures.batch2.build_synthetic_fixture import build_ordinary_fixture


def _cfg(
    *,
    fallback: bool = True,
    strict: bool = False,
    mode: str = "pose_balanced",
) -> EnhancementConfig:
    return EnhancementConfig.from_mapping(
        {
            "training": {"enabled": True, "metadata_sampling": True},
            "sampling": {"mode": mode, "fallback_mode": "legacy_random"},
            "runtime": {
                "fallback_on_optional_error": fallback,
                "strict_validation": strict,
            },
        }
    )


class TestBatch2FallbackExceptionBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="dfl_fallback_bounds_"))
        cls.ordinary_dir = cls.temp_dir / "ordinary"
        build_ordinary_fixture(cls.ordinary_dir)

    @classmethod
    def tearDownClass(cls):
        if cls.temp_dir.exists():
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_missing_metadata_fallback_true(self):
        rt = build_sampling_runtime("src", self.ordinary_dir, _cfg(fallback=True))
        self.assertEqual(rt.resolution.effective_mode, "legacy_random")
        self.assertTrue(rt.startup_log["fallback_on_optional_error"])
        self.assertFalse(rt.startup_log["strict_validation"])

    def test_missing_metadata_fallback_false_raises(self):
        with self.assertRaises(Exception):
            build_sampling_runtime("src", self.ordinary_dir, _cfg(fallback=False))

    def test_missing_metadata_strict_raises_even_if_fallback_true(self):
        with self.assertRaises(ValueError):
            build_sampling_runtime(
                "src", self.ordinary_dir, _cfg(fallback=True, strict=True)
            )

    def test_sample_loader_value_error_propagates(self):
        with mock.patch(
            "samplelib.sampling.runtime.SampleLoader.load",
            side_effect=ValueError("NO_TRAINING_SAMPLES"),
        ):
            with self.assertRaises(ValueError) as ctx:
                build_sampling_runtime("src", self.ordinary_dir, _cfg(fallback=True))
        self.assertIn("NO_TRAINING_SAMPLES", str(ctx.exception))

    def test_sample_loader_permission_error_propagates(self):
        with mock.patch(
            "samplelib.sampling.runtime.SampleLoader.load",
            side_effect=PermissionError("denied"),
        ):
            with self.assertRaises(PermissionError):
                build_sampling_runtime("dst", self.ordinary_dir, _cfg(fallback=True))

    def test_sample_loader_memory_error_propagates(self):
        with mock.patch(
            "samplelib.sampling.runtime.SampleLoader.load",
            side_effect=MemoryError("oom"),
        ):
            with self.assertRaises(MemoryError):
                build_sampling_runtime("src", self.ordinary_dir, _cfg(fallback=True))

    def test_sample_loader_runtime_error_propagates(self):
        with mock.patch(
            "samplelib.sampling.runtime.SampleLoader.load",
            side_effect=RuntimeError("packed-failure"),
        ):
            with self.assertRaises(RuntimeError):
                build_sampling_runtime("src", self.ordinary_dir, _cfg(fallback=True))

    def test_empty_samples_raises(self):
        with mock.patch(
            "samplelib.sampling.runtime.SampleLoader.load",
            return_value=[],
        ):
            with self.assertRaises(ValueError) as ctx:
                build_sampling_runtime("src", self.ordinary_dir, _cfg(fallback=True))
        self.assertIn("No training samples", str(ctx.exception))

    def test_src_dst_optional_isolation(self):
        """SRC optional missing Metadata can fallback while DST is independent."""
        src_rt = build_sampling_runtime("src", self.ordinary_dir, _cfg(fallback=True))
        dst_rt = build_sampling_runtime("dst", self.ordinary_dir, _cfg(fallback=True))
        self.assertEqual(src_rt.role, "src")
        self.assertEqual(dst_rt.role, "dst")
        self.assertEqual(src_rt.resolution.effective_mode, "legacy_random")
        self.assertEqual(dst_rt.resolution.effective_mode, "legacy_random")

    def test_src_core_failure_does_not_become_fallback(self):
        with mock.patch(
            "samplelib.sampling.runtime.SampleLoader.load",
            side_effect=RuntimeError("SRC_CORE"),
        ):
            with self.assertRaises(RuntimeError):
                build_sampling_runtime("src", self.ordinary_dir, _cfg(fallback=True))


if __name__ == "__main__":
    unittest.main()
