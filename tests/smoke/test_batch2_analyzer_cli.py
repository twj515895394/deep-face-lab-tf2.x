import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_strict_invalid_keeps_existing_sidecar_bytes(self):
        """strict invalid must not overwrite the formal Sidecar (T17-R1-02)."""
        work = self.temp_dir / "strict_keep"
        if work.exists():
            shutil.rmtree(work, ignore_errors=True)
        build_ordinary_fixture(work)
        meta_file = work / "faceset_metadata.v1.json"
        report_file = work / "faceset_metadata_report.v1.json"

        ret0 = FacesetAnalyzer.main(
            input_dir=work,
            output_file=meta_file,
            report_file=report_file,
            incremental=False,
            force=True,
        )
        self.assertEqual(ret0, 0)
        self.assertTrue(meta_file.exists())
        old_bytes = meta_file.read_bytes()
        old_sha = hashlib.sha256(old_bytes).hexdigest()

        from samplelib.metadata.analyzer import FacesetAnalyzer as AnalyzerCls

        real_analyze = AnalyzerCls.analyze_samples

        def _inject_invalid(self, samples, samples_path):
            res = real_analyze(self, samples, samples_path)
            summary = dict(res.metadata.summary or {})
            summary["invalid_samples"] = max(1, int(summary.get("invalid_samples", 0)) + 1)
            res.metadata.summary = summary
            if res.metadata.samples:
                sample0 = dict(res.metadata.samples[0])
                issues = list(sample0.get("issues") or [])
                issues.append("INJECTED_STRICT_INVALID")
                sample0["issues"] = issues
                res.metadata.samples = [sample0] + list(res.metadata.samples[1:])
            return res

        with mock.patch.object(AnalyzerCls, "analyze_samples", _inject_invalid):
            ret = FacesetAnalyzer.main(
                input_dir=work,
                output_file=meta_file,
                report_file=report_file,
                incremental=False,
                force=True,
                strict=True,
            )

        self.assertEqual(ret, 5)
        self.assertEqual(hashlib.sha256(meta_file.read_bytes()).hexdigest(), old_sha)
        self.assertEqual(meta_file.read_bytes(), old_bytes)

    def test_incremental_preserves_canonical_pose_contract(self):
        work = self.temp_dir / "incr_canonical"
        if work.exists():
            shutil.rmtree(work, ignore_errors=True)
        build_ordinary_fixture(work)
        meta_file = work / "faceset_metadata.v1.json"
        report_file = work / "faceset_metadata_report.v1.json"

        self.assertEqual(
            FacesetAnalyzer.main(
                input_dir=work,
                output_file=meta_file,
                report_file=report_file,
                incremental=False,
                force=True,
            ),
            0,
        )
        self.assertEqual(
            FacesetAnalyzer.main(
                input_dir=work,
                output_file=meta_file,
                report_file=report_file,
                incremental=True,
            ),
            0,
        )
        loaded, val = load_metadata(meta_file)
        self.assertTrue(val.is_valid)
        pose_cfg = (loaded.analysis_config or {}).get("pose") or {}
        self.assertEqual(pose_cfg.get("bucket_contract_version"), 1)
        self.assertIn("canonical_yaw_buckets", pose_cfg)
        self.assertIn("canonical_pitch_buckets", pose_cfg)
        self.assertGreaterEqual(len(pose_cfg.get("canonical_yaw_buckets") or []), 1)

    def test_full_incremental_no_change_exact_summary_parity(self):
        """T17-R2-01: full → incremental no-change must share canonical summary contract."""
        from samplelib.metadata.summary_builder import CANONICAL_SUMMARY_KEYS

        work = self.temp_dir / "incr_parity_no_change"
        if work.exists():
            shutil.rmtree(work, ignore_errors=True)
        build_ordinary_fixture(work)
        meta_file = work / "faceset_metadata.v1.json"
        report_file = work / "faceset_metadata_report.v1.json"

        self.assertEqual(
            FacesetAnalyzer.main(
                input_dir=work,
                output_file=meta_file,
                report_file=report_file,
                incremental=False,
                force=True,
                workers=1,
            ),
            0,
        )
        full_meta, full_val = load_metadata(meta_file)
        self.assertTrue(full_val.is_valid)
        full_summary = dict(full_meta.summary or {})
        full_fp = (full_meta.dataset or {}).get("fingerprint")
        full_keys = set(full_summary.keys())

        self.assertEqual(full_keys, set(CANONICAL_SUMMARY_KEYS))

        self.assertEqual(
            FacesetAnalyzer.main(
                input_dir=work,
                output_file=meta_file,
                report_file=report_file,
                incremental=True,
                workers=1,
            ),
            0,
        )
        incr_meta, incr_val = load_metadata(meta_file)
        self.assertTrue(incr_val.is_valid)
        incr_summary = dict(incr_meta.summary or {})
        incr_fp = (incr_meta.dataset or {}).get("fingerprint")

        self.assertEqual(set(incr_summary.keys()), set(CANONICAL_SUMMARY_KEYS))
        self.assertEqual(incr_summary["total_samples"], full_summary["total_samples"])
        self.assertEqual(incr_summary["valid_samples"], full_summary["valid_samples"])
        self.assertEqual(incr_summary["invalid_samples"], full_summary["invalid_samples"])
        self.assertEqual(incr_summary["yaw_bucket_counts"], full_summary["yaw_bucket_counts"])
        self.assertEqual(incr_summary["pitch_bucket_counts"], full_summary["pitch_bucket_counts"])
        self.assertEqual(incr_fp, full_fp)
        # Nested pose contract on every sample
        for s in incr_meta.samples:
            self.assertIn("pose", s)
            self.assertIn("yaw_bucket", s["pose"])
            self.assertIn("pitch_bucket", s["pose"])
            self.assertIn("quality", s)
            self.assertIn("quality_score", s["quality"])

    def test_incremental_partial_change_keeps_canonical_contract(self):
        """Partial recompute still emits Ticket 14 summary keys + nested pose/quality."""
        from samplelib.metadata.summary_builder import CANONICAL_SUMMARY_KEYS
        from samplelib import SampleLoader, SampleType

        work = self.temp_dir / "incr_parity_partial"
        if work.exists():
            shutil.rmtree(work, ignore_errors=True)
        build_ordinary_fixture(work)
        meta_file = work / "faceset_metadata.v1.json"
        report_file = work / "faceset_metadata_report.v1.json"

        self.assertEqual(
            FacesetAnalyzer.main(
                input_dir=work,
                output_file=meta_file,
                report_file=report_file,
                incremental=False,
                force=True,
                workers=1,
            ),
            0,
        )
        full_meta, _ = load_metadata(meta_file)
        full_fp = (full_meta.dataset or {}).get("fingerprint")

        samples = SampleLoader.load(SampleType.FACE, work)
        target = Path(samples[0].filename)
        original = target.read_bytes()
        try:
            mutated = bytearray(original)
            if len(mutated) > 10:
                mutated[10] = (mutated[10] + 1) % 256
                target.write_bytes(bytes(mutated))
            else:
                target.write_bytes(original + b"X")

            self.assertEqual(
                FacesetAnalyzer.main(
                    input_dir=work,
                    output_file=meta_file,
                    report_file=report_file,
                    incremental=True,
                    workers=1,
                ),
                0,
            )
            incr_meta, incr_val = load_metadata(meta_file)
            self.assertTrue(incr_val.is_valid)
            summary = dict(incr_meta.summary or {})
            self.assertEqual(set(summary.keys()), set(CANONICAL_SUMMARY_KEYS))
            self.assertEqual(summary["total_samples"], full_meta.summary["total_samples"])
            self.assertIn("yaw_bucket_counts", summary)
            self.assertIn("quality_stats", summary)
            self.assertIn("normalization", summary)
            # At least one sample changed content → dataset fingerprint must move.
            self.assertNotEqual((incr_meta.dataset or {}).get("fingerprint"), full_fp)
            for s in incr_meta.samples:
                self.assertIn("pose", s)
                self.assertIn("yaw_bucket", s["pose"])
        finally:
            target.write_bytes(original)

    def test_worker_fatal_keeps_existing_sidecar_bytes(self):
        """Worker/pool fatal must not overwrite formal Sidecar (T17-R2 failure sentinel)."""
        work = self.temp_dir / "worker_fatal_keep"
        if work.exists():
            shutil.rmtree(work, ignore_errors=True)
        build_ordinary_fixture(work)
        meta_file = work / "faceset_metadata.v1.json"
        report_file = work / "faceset_metadata_report.v1.json"

        ret0 = FacesetAnalyzer.main(
            input_dir=work,
            output_file=meta_file,
            report_file=report_file,
            incremental=False,
            force=True,
            workers=1,
        )
        self.assertEqual(ret0, 0)
        old_bytes = meta_file.read_bytes()
        old_sha = hashlib.sha256(old_bytes).hexdigest()

        from samplelib.metadata.analyzer import FacesetAnalyzer as AnalyzerCls

        def _boom(self, tasks, worker_count):
            raise RuntimeError("injected-worker-fatal")

        with mock.patch.object(AnalyzerCls, "_run_pass1", _boom):
            ret = FacesetAnalyzer.main(
                input_dir=work,
                output_file=meta_file,
                report_file=report_file,
                incremental=False,
                force=True,
                workers=2,
            )

        self.assertEqual(ret, 4)
        self.assertEqual(hashlib.sha256(meta_file.read_bytes()).hexdigest(), old_sha)
        self.assertEqual(meta_file.read_bytes(), old_bytes)

    def test_signature_mode_migration_plans(self):
        """quick→strong recompute; strong→quick forbidden; same-mode reuse allowed."""
        from samplelib.metadata.fingerprint import (
            SIGNATURE_MODE_QUICK,
            SIGNATURE_MODE_STRONG,
            signature_config_dict,
        )
        from samplelib.metadata.incremental import build_incremental_plan
        from samplelib.metadata.schema import FacesetMetadataV1

        samples = [
            {
                "sample_id": "00001",
                "sample_key": "a.png",
                "signature": {
                    "sample_key": "a.png",
                    "byte_size": 10,
                    "quick_hash": "abc",
                    "content_sha256": "def",
                },
            }
        ]
        quick_meta = FacesetMetadataV1(
            analyzer_version="v1.0",
            analysis_config={"signature": signature_config_dict(SIGNATURE_MODE_QUICK)},
            samples=samples,
        )
        strong_meta = FacesetMetadataV1(
            analyzer_version="v1.0",
            analysis_config={"signature": signature_config_dict(SIGNATURE_MODE_STRONG)},
            samples=samples,
        )
        cur = {"a.png": samples[0]["signature"]}

        plan_up = build_incremental_plan(
            quick_meta, cur, current_signature_mode=SIGNATURE_MODE_STRONG
        )
        self.assertFalse(plan_up.is_incremental)
        self.assertTrue(any("UPGRADE" in r for r in plan_up.reasons))

        plan_down = build_incremental_plan(
            strong_meta, cur, current_signature_mode=SIGNATURE_MODE_QUICK
        )
        self.assertFalse(plan_down.is_incremental)
        self.assertTrue(any("DOWNGRADE" in r for r in plan_down.reasons))

        plan_same = build_incremental_plan(
            quick_meta, cur, current_signature_mode=SIGNATURE_MODE_QUICK
        )
        self.assertTrue(plan_same.is_incremental)
        self.assertEqual(plan_same.reused_sample_keys, ["a.png"])


if __name__ == "__main__":
    unittest.main()
