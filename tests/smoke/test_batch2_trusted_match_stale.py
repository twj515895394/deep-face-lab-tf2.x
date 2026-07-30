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

    def test_unsigned_legacy_record_not_trusted(self):
        """ID hit without signature: record_matched, not trusted, no pose/quality load."""
        from samplelib import SampleLoader, SampleType
        from samplelib.metadata.schema import FacesetMetadataV1

        analyzer = FacesetAnalyzer(FacesetAnalyzerConfig(workers=1, strong_fingerprint=False))
        res = analyzer.analyze(self.ordinary_dir)
        # Strip all per-sample signatures to simulate legacy unsigned sidecar.
        unsigned_samples = []
        for rec in res.metadata.samples:
            r = dict(rec)
            r.pop("signature", None)
            unsigned_samples.append(r)
        meta = FacesetMetadataV1(
            schema_version=res.metadata.schema_version,
            analyzer_version=res.metadata.analyzer_version,
            dataset=dict(res.metadata.dataset or {}),
            analysis_config=dict(res.metadata.analysis_config or {}),
            summary=dict(res.metadata.summary or {}),
            samples=unsigned_samples,
        )
        meta_path = self.ordinary_dir / "faceset_metadata.v1.json"
        meta.dump_json(meta_path)

        samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        runtime = FacesetMetadataLoader.load(self.ordinary_dir, samples, metadata_path=meta_path)

        self.assertGreaterEqual(runtime.id_matched_count, 1)
        self.assertTrue(np.any(runtime.record_matched))
        self.assertEqual(runtime.trusted_matched_count, 0)
        self.assertEqual(runtime.signature_matched_count, 0)
        self.assertGreaterEqual(runtime.unsigned_signature_count, 1)
        self.assertFalse(np.any(runtime.pose_valid))
        self.assertFalse(np.any(runtime.quality_valid))
        self.assertTrue(any("UNSIGNED_SIGNATURE" in w for w in runtime.warnings))


if __name__ == "__main__":
    unittest.main()
