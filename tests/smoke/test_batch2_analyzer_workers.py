"""Ticket 17: analyzer workers and deterministic multi-process output."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from samplelib.metadata.analyzer import FacesetAnalyzer, FacesetAnalyzerConfig, resolve_worker_count
from samplelib.metadata.fingerprint import SIGNATURE_MODE_STRONG
from tests.fixtures.batch2.build_synthetic_fixture import build_ordinary_fixture, build_packed_fixture


class TestBatch2AnalyzerWorkers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="dfl_analyzer_workers_"))
        cls.ordinary_dir = cls.temp_dir / "ordinary"
        cls.packed_dir = cls.temp_dir / "packed"
        cls.unicode_dir = cls.temp_dir / "分析 中文"
        build_ordinary_fixture(cls.ordinary_dir)
        build_packed_fixture(cls.ordinary_dir, cls.packed_dir)
        build_ordinary_fixture(cls.unicode_dir)

    @classmethod
    def tearDownClass(cls):
        if cls.temp_dir.exists():
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_resolve_worker_count(self):
        self.assertEqual(resolve_worker_count(1), 1)
        self.assertEqual(resolve_worker_count(2), 2)
        self.assertGreaterEqual(resolve_worker_count(None), 1)
        self.assertLessEqual(resolve_worker_count(None), 8)
        with self.assertRaises(ValueError):
            resolve_worker_count(0)
        with self.assertRaises(ValueError):
            resolve_worker_count(-3)

    def test_workers_1_and_2_same_fingerprint_ordinary(self):
        a1 = FacesetAnalyzer(FacesetAnalyzerConfig(workers=1, strong_fingerprint=False))
        a2 = FacesetAnalyzer(FacesetAnalyzerConfig(workers=2, strong_fingerprint=False))
        r1 = a1.analyze(self.ordinary_dir)
        r2 = a2.analyze(self.ordinary_dir)
        self.assertEqual(r1.metadata.dataset["fingerprint"], r2.metadata.dataset["fingerprint"])
        self.assertEqual(r1.summary["total_samples"], r2.summary["total_samples"])
        self.assertEqual(r1.timing["workers_used"], 1)
        self.assertEqual(r2.timing["workers_used"], 2)
        # sample order deterministic by sample_id
        ids1 = [s["sample_id"] for s in r1.metadata.samples]
        ids2 = [s["sample_id"] for s in r2.metadata.samples]
        self.assertEqual(ids1, ids2)
        self.assertEqual(ids1, sorted(ids1))
        sig_cfg = r1.metadata.analysis_config.get("signature", {})
        self.assertEqual(sig_cfg.get("mode"), "quick")
        self.assertEqual(r1.metadata.analysis_config["workers"]["used"], 1)
        self.assertEqual(r2.metadata.analysis_config["workers"]["used"], 2)

    def test_workers_packed_strong(self):
        analyzer = FacesetAnalyzer(
            FacesetAnalyzerConfig(workers=2, strong_fingerprint=True)
        )
        res = analyzer.analyze(self.packed_dir)
        self.assertEqual(res.timing["signature_mode"], SIGNATURE_MODE_STRONG)
        self.assertEqual(res.metadata.analysis_config["signature"]["mode"], "strong")
        for s in res.metadata.samples:
            self.assertIsNotNone(s["signature"].get("content_sha256"))

    def test_workers_unicode_dir(self):
        analyzer = FacesetAnalyzer(FacesetAnalyzerConfig(workers=2))
        res = analyzer.analyze(self.unicode_dir)
        self.assertGreater(res.summary["total_samples"], 0)
        self.assertEqual(res.timing["workers_used"], 2)

    def test_auto_workers_records_used(self):
        analyzer = FacesetAnalyzer(FacesetAnalyzerConfig(workers=None))
        res = analyzer.analyze(self.ordinary_dir)
        self.assertIn("workers_used", res.timing)
        self.assertGreaterEqual(res.timing["workers_used"], 1)


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    unittest.main()
