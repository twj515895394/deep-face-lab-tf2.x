"""Ticket 17: trusted match and same-name replacement stale detection."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from samplelib.metadata.analyzer import FacesetAnalyzer, FacesetAnalyzerConfig
from samplelib.metadata.loader import FacesetMetadataLoader, FacesetMetadataStatus
from tests.fixtures.batch2.build_synthetic_fixture import build_ordinary_fixture


class TestBatch2TrustedMatchStale(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dfl_trusted_match_"))
        self.ordinary_dir = self.temp_dir / "ordinary"
        build_ordinary_fixture(self.ordinary_dir)

    def tearDown(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_perfect_trusted_match(self):
        from samplelib import SampleLoader, SampleType

        analyzer = FacesetAnalyzer(FacesetAnalyzerConfig(workers=1, strong_fingerprint=True))
        res = analyzer.analyze(self.ordinary_dir)
        meta_path = self.ordinary_dir / "faceset_metadata.v1.json"
        res.metadata.dump_json(meta_path)

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples, metadata_path=meta_path)
        self.assertEqual(runtime.status, FacesetMetadataStatus.LOADED)
        self.assertEqual(runtime.trusted_matched_count, len(samples))
        self.assertEqual(runtime.stale_signature_count, 0)
        self.assertEqual(runtime.matched_count, runtime.trusted_matched_count)
        self.assertTrue(np.any(runtime.pose_valid))

    def test_same_name_replace_becomes_stale(self):
        from samplelib import SampleLoader, SampleType

        analyzer = FacesetAnalyzer(FacesetAnalyzerConfig(workers=1, strong_fingerprint=True))
        res = analyzer.analyze(self.ordinary_dir)
        meta_path = self.ordinary_dir / "faceset_metadata.v1.json"
        res.metadata.dump_json(meta_path)

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        # Pick first real image file (skip corrupt if present)
        target = None
        for s in samples:
            p = Path(s.filename)
            if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png"):
                target = p
                break
        self.assertIsNotNone(target)
        original = target.read_bytes()
        try:
            mutated = bytearray(original)
            if len(mutated) > 20:
                mutated[20] = (mutated[20] + 7) % 256
                target.write_bytes(bytes(mutated))
            else:
                target.write_bytes(original + b"\x01")

            samples2 = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
            runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples2, metadata_path=meta_path)

            self.assertGreaterEqual(runtime.id_matched_count, 1)
            self.assertGreaterEqual(runtime.stale_signature_count, 1)
            self.assertLess(runtime.trusted_matched_count, runtime.id_matched_count)
            # record_matched remains True for id hits (Ticket 14); trusted pose/quality stay neutral.
            self.assertTrue(np.any(runtime.record_matched))
            self.assertLess(int(np.sum(runtime.pose_valid)), runtime.id_matched_count)
            self.assertLess(int(np.sum(runtime.quality_valid)), runtime.id_matched_count)
        finally:
            target.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
