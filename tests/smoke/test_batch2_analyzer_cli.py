import json
import shutil
import tempfile
import unittest
from pathlib import Path

from mainscripts import FacesetAnalyzer
from samplelib.metadata.store import load_metadata
from tests.fixtures.batch2.build_synthetic_fixture import (
    build_ordinary_fixture,
    build_packed_fixture,
)


class TestFacesetAnalyzerCLI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="dfl_cli_test_"))
        cls.ordinary_dir = cls.temp_dir / "ordinary"
        cls.packed_dir = cls.temp_dir / "packed"

        build_ordinary_fixture(cls.ordinary_dir)
        build_packed_fixture(cls.ordinary_dir, cls.packed_dir)

    @classmethod
    def tearDownClass(cls):
        if cls.temp_dir.exists():
            shutil.rmtree(cls.temp_dir)

    def test_cli_full_analysis(self):
        meta_file = self.ordinary_dir / "faceset_metadata.v1.json"
        report_file = self.ordinary_dir / "faceset_metadata_report.v1.json"

        ret = FacesetAnalyzer.main(
            input_dir=self.ordinary_dir,
            output_file=meta_file,
            report_file=report_file,
            incremental=False,
        )

        self.assertEqual(ret, 0)
        self.assertTrue(meta_file.exists())
        self.assertTrue(report_file.exists())

        loaded_meta, val_res = load_metadata(meta_file)
        self.assertTrue(val_res.is_valid)
        self.assertGreaterEqual(len(loaded_meta.samples), 10)

        with open(report_file, "r", encoding="utf-8") as f:
            report_data = json.load(f)

        self.assertGreaterEqual(report_data["total_samples"], 10)
        self.assertEqual(report_data["faceset_format"], "ordinary")

    def test_cli_incremental_analysis(self):
        meta_file = self.ordinary_dir / "faceset_metadata.v1.json"
        report_file = self.ordinary_dir / "faceset_metadata_report.v1.json"

        # 1. Full run
        ret1 = FacesetAnalyzer.main(
            input_dir=self.ordinary_dir,
            output_file=meta_file,
            report_file=report_file,
            incremental=False,
        )
        self.assertEqual(ret1, 0)

        # 2. Incremental run (without file modifications)
        ret2 = FacesetAnalyzer.main(
            input_dir=self.ordinary_dir,
            output_file=meta_file,
            report_file=report_file,
            incremental=True,
        )
        self.assertEqual(ret2, 0)

        with open(report_file, "r", encoding="utf-8") as f:
            report_data = json.load(f)

        self.assertTrue(report_data["incremental"])
        self.assertGreaterEqual(report_data["reused_count"], 10)

    def test_cli_packed_faceset(self):
        meta_file = self.packed_dir / "faceset_metadata.v1.json"
        report_file = self.packed_dir / "faceset_metadata_report.v1.json"

        ret = FacesetAnalyzer.main(
            input_dir=self.packed_dir,
            output_file=meta_file,
            report_file=report_file,
            incremental=False,
        )

        self.assertEqual(ret, 0)
        self.assertTrue(meta_file.exists())

        with open(report_file, "r", encoding="utf-8") as f:
            report_data = json.load(f)

        self.assertEqual(report_data["faceset_format"], "packed")
        self.assertEqual(report_data["total_samples"], 10)


if __name__ == "__main__":
    unittest.main()
