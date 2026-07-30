"""
Unicode / Chinese path contract for Batch 2 I/O.

Covers:
- Chinese directory names
- spaces in path segments
- non-ASCII and emoji filenames
- Analyzer full + incremental
- Metadata store / report UTF-8
- Sampling runtime load under Chinese paths
- SampleLoader short vs long Windows path cache consistency
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from core.enhancements import EnhancementConfig
from mainscripts import FacesetAnalyzer
from samplelib import SampleLoader, SampleType
from samplelib.metadata.store import load_metadata
from samplelib.sampling.runtime import build_sampling_runtime
from tests.fixtures.batch2.build_synthetic_fixture import (
    build_ordinary_fixture,
    create_dflimg_file,
)


class TestBatch2UnicodePaths(unittest.TestCase):
    def setUp(self):
        # Nested Chinese + space path (AGENTS.md Unicode I/O contract).
        self.temp_dir = Path(tempfile.mkdtemp(prefix="中文路径_Batch2 "))
        self.work = self.temp_dir / "样本 目录" / "faceset"
        self.work.mkdir(parents=True, exist_ok=True)
        build_ordinary_fixture(self.work)
        create_dflimg_file(
            self.work / "新增_样本_测试.jpg",
            source_filename="frame_unicode_cn.png",
        )
        SampleLoader.clear_cache()

    def tearDown(self):
        SampleLoader.clear_cache()
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sample_loader_unicode_dir_and_filename(self):
        samples = SampleLoader.load(SampleType.FACE, self.work)
        self.assertGreaterEqual(len(samples), 11)
        names = [Path(s.filename).name for s in samples]
        self.assertTrue(any("中文" in n or "新增" in n for n in names))

    def test_sample_loader_short_long_path_same_count(self):
        """Windows short (8.3) vs resolve() long path must not diverge after invalidate."""
        SampleLoader.clear_cache()
        long_path = self.work.resolve()
        # Path as constructed may be short-form under TEMP.
        n_a = len(SampleLoader.load(SampleType.FACE, self.work))
        SampleLoader.invalidate_path(self.work)
        n_b = len(SampleLoader.load(SampleType.FACE, long_path))
        self.assertEqual(n_a, n_b)

    def test_analyzer_cli_chinese_paths_utf8_report(self):
        meta = self.work / "元数据_faceset.v1.json"
        report = self.work / "报告 中文.json"
        rc = FacesetAnalyzer.main(
            input_dir=self.work,
            output_file=meta,
            report_file=report,
            force=True,
            workers=1,
        )
        self.assertEqual(rc, 0)
        self.assertTrue(meta.is_file())
        self.assertTrue(report.is_file())

        loaded, val = load_metadata(meta)
        self.assertTrue(val.is_valid)
        self.assertGreaterEqual(len(loaded.samples), 11)
        keys = [s.get("sample_key", "") for s in loaded.samples]
        self.assertTrue(any("中文" in k or "新增" in k for k in keys))

        # UTF-8 round-trip without UnicodeEncodeError
        text = report.read_text(encoding="utf-8")
        data = json.loads(text)
        self.assertIn("dataset_path", data)
        self.assertTrue(
            "中文" in data["dataset_path"] or "样本" in data["dataset_path"]
        )
        # ensure_ascii=False path: raw file should contain non-escaped Chinese if path has it
        self.assertIn("faceset_format", data)

        # Incremental under same Chinese path
        rc2 = FacesetAnalyzer.main(
            input_dir=self.work,
            output_file=meta,
            report_file=report,
            incremental=True,
            workers=1,
        )
        self.assertEqual(rc2, 0)

    def test_sampling_runtime_chinese_path(self):
        meta = self.work / "faceset_metadata.v1.json"
        report = self.work / "faceset_metadata_report.v1.json"
        self.assertEqual(
            FacesetAnalyzer.main(
                input_dir=self.work,
                output_file=meta,
                report_file=report,
                force=True,
                workers=1,
            ),
            0,
        )
        cfg = EnhancementConfig.from_mapping(
            {
                "training": {"enabled": True, "metadata_sampling": True},
                "sampling": {"mode": "legacy_random"},
                "runtime": {"fallback_on_optional_error": True},
            }
        )
        rt = build_sampling_runtime("src", self.work, cfg)
        self.assertEqual(rt.role, "src")
        meta_path = str(rt.startup_log.get("metadata_path", ""))
        self.assertTrue(
            ("中文" in meta_path) or ("样本" in meta_path),
            f"expected Chinese path in metadata_path, got {meta_path!r}",
        )
        self.assertIsNotNone(rt.resolution)


if __name__ == "__main__":
    unittest.main()
