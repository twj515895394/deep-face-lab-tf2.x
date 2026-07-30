"""Ticket 18: full vs incremental equivalence on real Analyzer records."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from mainscripts import FacesetAnalyzer
from samplelib.metadata.store import load_metadata
from samplelib.metadata.summary_builder import CANONICAL_SUMMARY_KEYS
from tests.fixtures.batch2.build_synthetic_fixture import (
    build_ordinary_fixture,
    build_packed_fixture,
)

# Fields allowed to differ between incremental and force-full runs.
_ALLOWED_DIFF_TOP = {
    "created_at",
    "elapsed",
    "timing",
}


def _finite_float_equal(a: float, b: float, tol: float = 1e-6) -> bool:
    if not (math.isfinite(a) and math.isfinite(b)):
        return a == b
    return abs(a - b) <= tol


def _compare_jsonish(a: Any, b: Any, path: str, diffs: List[str], tol: float = 1e-6) -> None:
    if type(a) != type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        diffs.append(f"{path}: type {type(a).__name__} != {type(b).__name__}")
        return
    if isinstance(a, dict):
        keys = set(a.keys()) | set(b.keys())
        for k in sorted(keys):
            if k not in a:
                diffs.append(f"{path}.{k}: missing in left")
                continue
            if k not in b:
                diffs.append(f"{path}.{k}: missing in right")
                continue
            _compare_jsonish(a[k], b[k], f"{path}.{k}", diffs, tol=tol)
        return
    if isinstance(a, list):
        if len(a) != len(b):
            diffs.append(f"{path}: list len {len(a)} != {len(b)}")
            return
        for i, (x, y) in enumerate(zip(a, b)):
            _compare_jsonish(x, y, f"{path}[{i}]", diffs, tol=tol)
        return
    if isinstance(a, float) or isinstance(b, float):
        try:
            if not _finite_float_equal(float(a), float(b), tol=tol):
                diffs.append(f"{path}: {a} != {b}")
        except (TypeError, ValueError):
            if a != b:
                diffs.append(f"{path}: {a!r} != {b!r}")
        return
    if a != b:
        diffs.append(f"{path}: {a!r} != {b!r}")


def _sample_core(rec: dict) -> dict:
    """Comparable subset of a sample record (exclude volatile fields)."""
    return {
        "sample_id": rec.get("sample_id"),
        "sample_key": rec.get("sample_key"),
        "signature": rec.get("signature"),
        "image": rec.get("image"),
        "landmarks": rec.get("landmarks"),
        "pose": rec.get("pose"),
        "quality_raw": rec.get("quality_raw"),
        "quality": rec.get("quality"),
        "issues": rec.get("issues") or [],
    }


def assert_metadata_equivalent(meta_a, meta_b, *, label: str = "") -> None:
    diffs: List[str] = []
    if meta_a.schema_version != meta_b.schema_version:
        diffs.append(f"schema_version {meta_a.schema_version} != {meta_b.schema_version}")
    if meta_a.analyzer_version != meta_b.analyzer_version:
        diffs.append(f"analyzer_version {meta_a.analyzer_version} != {meta_b.analyzer_version}")

    ds_a = dict(meta_a.dataset or {})
    ds_b = dict(meta_b.dataset or {})
    for k in ("format", "fingerprint", "sample_count"):
        if ds_a.get(k) != ds_b.get(k):
            diffs.append(f"dataset.{k}: {ds_a.get(k)!r} != {ds_b.get(k)!r}")

    sa = dict(meta_a.summary or {})
    sb = dict(meta_b.summary or {})
    if set(sa.keys()) != set(CANONICAL_SUMMARY_KEYS):
        diffs.append(f"summary keys A {set(sa.keys())} != canonical")
    if set(sb.keys()) != set(CANONICAL_SUMMARY_KEYS):
        diffs.append(f"summary keys B {set(sb.keys())} != canonical")
    for k in CANONICAL_SUMMARY_KEYS:
        if k == "normalization":
            _compare_jsonish(sa.get(k), sb.get(k), f"summary.{k}", diffs, tol=1e-5)
        elif k == "quality_stats":
            _compare_jsonish(sa.get(k), sb.get(k), f"summary.{k}", diffs, tol=1e-5)
        else:
            _compare_jsonish(sa.get(k), sb.get(k), f"summary.{k}", diffs, tol=1e-9)

    samples_a = list(meta_a.samples or [])
    samples_b = list(meta_b.samples or [])
    if len(samples_a) != len(samples_b):
        diffs.append(f"sample count {len(samples_a)} != {len(samples_b)}")
    else:
        ids_a = [s.get("sample_id") for s in samples_a]
        ids_b = [s.get("sample_id") for s in samples_b]
        if ids_a != ids_b:
            diffs.append(f"sample_id order/set differ: {ids_a} vs {ids_b}")
        for i, (ra, rb) in enumerate(zip(samples_a, samples_b)):
            _compare_jsonish(_sample_core(ra), _sample_core(rb), f"samples[{i}]", diffs, tol=1e-5)

    if diffs:
        raise AssertionError(f"{label} equivalence failed:\n- " + "\n- ".join(diffs[:40]))


class TestBatch2IncrementalFullEquivalence(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dfl_incr_equiv_"))

    def tearDown(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _run_cli(
        self,
        work: Path,
        *,
        incremental: bool = False,
        force: bool = False,
        strong: bool = False,
        workers: int = 1,
    ) -> int:
        meta = work / "faceset_metadata.v1.json"
        report = work / "faceset_metadata_report.v1.json"
        return FacesetAnalyzer.main(
            input_dir=work,
            output_file=meta,
            report_file=report,
            incremental=incremental,
            force=force,
            strong_fingerprint=strong,
            workers=workers,
        )

    def test_no_change_incremental_matches_full(self):
        work = self.temp_dir / "no_change"
        build_ordinary_fixture(work)
        self.assertEqual(self._run_cli(work, force=True), 0)
        full, _ = load_metadata(work / "faceset_metadata.v1.json")
        self.assertEqual(self._run_cli(work, incremental=True), 0)
        incr, val = load_metadata(work / "faceset_metadata.v1.json")
        self.assertTrue(val.is_valid)
        assert_metadata_equivalent(full, incr, label="no-change")
        with open(work / "faceset_metadata_report.v1.json", "r", encoding="utf-8") as f:
            rep = json.load(f)
        self.assertTrue(rep.get("incremental"))
        self.assertEqual(int(rep.get("recomputed_count") or 0), 0)
        self.assertGreaterEqual(int(rep.get("reused_count") or 0), 1)
        self.assertEqual(int(rep.get("stale_signature_count") or 0), 0)
        # Report must mirror Metadata summary usable/valid counts.
        self.assertEqual(rep["total_samples"], incr.summary["total_samples"])
        self.assertEqual(rep["invalid_samples"], incr.summary["invalid_samples"])
        self.assertEqual(rep["valid_image_samples"], incr.summary["valid_image_samples"])
        self.assertEqual(rep["usable_pose_samples"], incr.summary["usable_pose_samples"])

    def test_add_sample_incremental_matches_force_full(self):
        from tests.fixtures.batch2.build_synthetic_fixture import create_dflimg_file
        from facelib import FaceType

        work = self.temp_dir / "add_one"
        build_ordinary_fixture(work)
        self.assertEqual(self._run_cli(work, force=True), 0)
        full0, _ = load_metadata(work / "faceset_metadata.v1.json")
        n0 = len(full0.samples)

        # Brand-new DFL face (unique source_filename) so loader treats it as a new sample.
        create_dflimg_file(
            work / "added_face_99.jpg",
            img_type="clear",
            pose_type="center",
            face_type=FaceType.FULL,
            source_filename="frame_added_99.png",
        )

        self.assertEqual(self._run_cli(work, incremental=True), 0)
        incr, _ = load_metadata(work / "faceset_metadata.v1.json")
        with open(work / "faceset_metadata_report.v1.json", "r", encoding="utf-8") as f:
            rep = json.load(f)
        self.assertEqual(int(rep.get("added_count") or 0), 1)
        self.assertEqual(len(incr.samples), n0 + 1)

        self.assertEqual(self._run_cli(work, force=True), 0)
        full, _ = load_metadata(work / "faceset_metadata.v1.json")
        assert_metadata_equivalent(incr, full, label="add-one")

    def test_modify_same_name_recompute_one(self):
        from samplelib import SampleLoader, SampleType
        from tests.fixtures.batch2.build_synthetic_fixture import create_dflimg_file
        from facelib import FaceType

        work = self.temp_dir / "modify_one"
        build_ordinary_fixture(work)
        self.assertEqual(self._run_cli(work, force=True), 0)
        full0, _ = load_metadata(work / "faceset_metadata.v1.json")
        n0 = len(full0.samples)

        samples = SampleLoader.load(SampleType.FACE, work)
        target = Path(samples[0].filename)
        # Rewrite same path as a valid DFL face with different content/hash.
        create_dflimg_file(
            target,
            img_type="blur",
            pose_type="minor_left",
            face_type=FaceType.FULL,
            source_filename="frame_mutated_same_name.png",
        )
        SampleLoader.clear_cache()

        self.assertEqual(self._run_cli(work, incremental=True), 0)
        incr, _ = load_metadata(work / "faceset_metadata.v1.json")
        with open(work / "faceset_metadata_report.v1.json", "r", encoding="utf-8") as f:
            rep = json.load(f)
        self.assertEqual(int(rep.get("recomputed_count") or 0), 1)
        self.assertEqual(int(rep.get("reused_count") or 0), n0 - 1)
        self.assertEqual(int(rep.get("stale_signature_count") or 0), 1)

        self.assertEqual(self._run_cli(work, force=True), 0)
        full, _ = load_metadata(work / "faceset_metadata.v1.json")
        assert_metadata_equivalent(incr, full, label="modify-one")
        self.assertNotEqual(
            (full.dataset or {}).get("fingerprint"),
            (full0.dataset or {}).get("fingerprint"),
        )

    def test_delete_sample_removed(self):
        from samplelib import SampleLoader, SampleType
        from samplelib.metadata.identity import build_sample_key

        work = self.temp_dir / "delete_one"
        build_ordinary_fixture(work)
        self.assertEqual(self._run_cli(work, force=True), 0)
        full0, _ = load_metadata(work / "faceset_metadata.v1.json")
        n0 = len(full0.samples)
        samples = SampleLoader.load(SampleType.FACE, work)
        victim_sample = samples[0]
        victim_path = Path(victim_sample.filename)
        victim_key = build_sample_key(
            victim_sample.filename, is_packed=False, faceset_root=work
        )
        self.assertTrue(victim_path.is_file())
        victim_path.unlink()
        self.assertFalse(victim_path.exists())

        self.assertEqual(self._run_cli(work, incremental=True), 0)
        incr, _ = load_metadata(work / "faceset_metadata.v1.json")
        with open(work / "faceset_metadata_report.v1.json", "r", encoding="utf-8") as f:
            rep = json.load(f)
        # Deleted sample must not remain as a live record.
        incr_keys = {s.get("sample_key") for s in incr.samples}
        self.assertNotIn(victim_key, incr_keys)
        self.assertEqual(len(incr.samples), n0 - 1)
        # Prefer plan removed_count; allow recompute-path implementations only if
        # final samples already dropped the key (should not happen).
        self.assertGreaterEqual(int(rep.get("removed_count") or 0), 1)

        self.assertEqual(self._run_cli(work, force=True), 0)
        full, _ = load_metadata(work / "faceset_metadata.v1.json")
        assert_metadata_equivalent(incr, full, label="delete-one")

    def test_packed_no_change_equivalence(self):
        ordinary = self.temp_dir / "ord_for_pak"
        packed = self.temp_dir / "packed"
        build_ordinary_fixture(ordinary)
        build_packed_fixture(ordinary, packed)
        self.assertEqual(self._run_cli(packed, force=True), 0)
        full, _ = load_metadata(packed / "faceset_metadata.v1.json")
        self.assertEqual(self._run_cli(packed, incremental=True), 0)
        incr, _ = load_metadata(packed / "faceset_metadata.v1.json")
        assert_metadata_equivalent(full, incr, label="packed-no-change")

    def test_unicode_dir_no_change_equivalence(self):
        work = self.temp_dir / "中文 增量 测试"
        build_ordinary_fixture(work)
        self.assertEqual(self._run_cli(work, force=True), 0)
        full, _ = load_metadata(work / "faceset_metadata.v1.json")
        self.assertEqual(self._run_cli(work, incremental=True), 0)
        incr, _ = load_metadata(work / "faceset_metadata.v1.json")
        assert_metadata_equivalent(full, incr, label="unicode-no-change")


if __name__ == "__main__":
    unittest.main()
