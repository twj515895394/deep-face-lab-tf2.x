"""Ticket 17: quick/strong sample signatures and dataset fingerprints."""

from __future__ import annotations

import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from samplelib.metadata.fingerprint import (
    SIGNATURE_MODE_QUICK,
    SIGNATURE_MODE_STRONG,
    build_dataset_fingerprint,
    build_signature_from_sample,
    compute_content_sha256,
    compute_quick_hash,
    signatures_match,
)
from tests.fixtures.batch2.build_synthetic_fixture import build_ordinary_fixture, build_packed_fixture


class TestBatch2FingerprintStrong(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="dfl_fp_strong_"))
        cls.ordinary_dir = cls.temp_dir / "ordinary"
        cls.packed_dir = cls.temp_dir / "packed"
        cls.unicode_dir = cls.temp_dir / "中文 路径 test"
        build_ordinary_fixture(cls.ordinary_dir)
        build_packed_fixture(cls.ordinary_dir, cls.packed_dir)
        build_ordinary_fixture(cls.unicode_dir)

    @classmethod
    def tearDownClass(cls):
        if cls.temp_dir.exists():
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _first_sample(self, path: Path):
        from samplelib import SampleLoader, SampleType

        samples = SampleLoader.load(SampleType.FACE, path)
        self.assertGreater(len(samples), 0)
        return samples[0], samples

    def test_ordinary_quick_stable(self):
        sample, _ = self._first_sample(self.ordinary_dir)
        from samplelib.metadata.identity import build_sample_key

        key = build_sample_key(sample.filename, is_packed=False, faceset_root=self.ordinary_dir)
        s1 = build_signature_from_sample(sample, key, self.ordinary_dir, mode=SIGNATURE_MODE_QUICK)
        s2 = build_signature_from_sample(sample, key, self.ordinary_dir, mode=SIGNATURE_MODE_QUICK)
        self.assertEqual(s1.to_dict(), s2.to_dict())
        self.assertIsNotNone(s1.quick_hash)
        self.assertIsNone(s1.content_sha256)

    def test_ordinary_strong_stable_and_content_sensitive(self):
        from samplelib import SampleLoader, SampleType
        from samplelib.metadata.identity import build_sample_key

        sample, _ = self._first_sample(self.ordinary_dir)
        key = build_sample_key(sample.filename, is_packed=False, faceset_root=self.ordinary_dir)
        s1 = build_signature_from_sample(sample, key, self.ordinary_dir, mode=SIGNATURE_MODE_STRONG)
        s2 = build_signature_from_sample(sample, key, self.ordinary_dir, mode=SIGNATURE_MODE_STRONG)
        self.assertEqual(s1.content_sha256, s2.content_sha256)
        self.assertIsNotNone(s1.content_sha256)

        # Same path: mutate file content, keep name.
        path = Path(sample.filename)
        original = path.read_bytes()
        try:
            mutated = bytearray(original)
            if len(mutated) > 10:
                mutated[10] = (mutated[10] + 1) % 256
                path.write_bytes(bytes(mutated))
            else:
                path.write_bytes(original + b"X")
            target = None
            for s in SampleLoader.load(SampleType.FACE, self.ordinary_dir):
                if Path(s.filename).name == path.name:
                    target = s
                    break
            self.assertIsNotNone(target)
            s3 = build_signature_from_sample(target, key, self.ordinary_dir, mode=SIGNATURE_MODE_STRONG)
            self.assertNotEqual(s1.content_sha256, s3.content_sha256)
        finally:
            path.write_bytes(original)

    def test_strong_hash_ignores_mtime_only_touch(self):
        sample, _ = self._first_sample(self.ordinary_dir)
        from samplelib.metadata.identity import build_sample_key

        key = build_sample_key(sample.filename, is_packed=False, faceset_root=self.ordinary_dir)
        s1 = build_signature_from_sample(sample, key, self.ordinary_dir, mode=SIGNATURE_MODE_STRONG)
        path = Path(sample.filename)
        os.utime(path, (path.stat().st_atime + 10, path.stat().st_mtime + 10))
        s2 = build_signature_from_sample(sample, key, self.ordinary_dir, mode=SIGNATURE_MODE_STRONG)
        self.assertEqual(s1.content_sha256, s2.content_sha256)

    def test_packed_strong(self):
        from samplelib import SampleLoader, SampleType
        from samplelib.metadata.identity import build_sample_key

        samples = SampleLoader.load(SampleType.FACE, self.packed_dir)
        self.assertGreater(len(samples), 0)
        sample = samples[0]
        key = build_sample_key(sample.filename, is_packed=True, faceset_root=self.packed_dir)
        sig = build_signature_from_sample(sample, key, self.packed_dir, mode=SIGNATURE_MODE_STRONG)
        self.assertIsNotNone(sig.content_sha256)
        self.assertIsNotNone(sig.packed_offset)
        self.assertTrue(signatures_match(sig.to_dict(), sig, mode=SIGNATURE_MODE_STRONG))

    def test_unicode_path_quick(self):
        sample, _ = self._first_sample(self.unicode_dir)
        from samplelib.metadata.identity import build_sample_key

        key = build_sample_key(sample.filename, is_packed=False, faceset_root=self.unicode_dir)
        sig = build_signature_from_sample(sample, key, self.unicode_dir, mode=SIGNATURE_MODE_QUICK)
        self.assertIsNotNone(sig.quick_hash)

    def test_dataset_fingerprint_order_independent(self):
        raw = b"abc" * 100
        q = compute_quick_hash(raw)
        c = compute_content_sha256(raw)
        from samplelib.metadata.fingerprint import SampleSignature

        a = SampleSignature("b.jpg", 300, quick_hash=q, content_sha256=c)
        b = SampleSignature("a.jpg", 300, quick_hash=q, content_sha256=c)
        fp1 = build_dataset_fingerprint([a, b])
        fp2 = build_dataset_fingerprint([b, a])
        self.assertEqual(fp1, fp2)


if __name__ == "__main__":
    unittest.main()
