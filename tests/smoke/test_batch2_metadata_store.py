import json
import tempfile
import unittest
from pathlib import Path

from samplelib.metadata.schema import FacesetMetadataV1
from samplelib.metadata.store import (
    AtomicWriteResult,
    MetadataStoreError,
    load_metadata,
    write_metadata_atomic,
)


class TestMetadataStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_write_metadata_atomic_new_file(self):
        meta = FacesetMetadataV1(
            analyzer_version="v1.0",
            samples=[
                {
                    "sample_id": "00001",
                    "sample_key": "img_00001.png",
                    "signature": "sig123",
                }
            ],
        )
        target_path = self.test_dir / "faceset_metadata.v1.json"

        result = write_metadata_atomic(target_path, meta, keep_backup=True)

        self.assertEqual(result.target_path, target_path.resolve())
        self.assertIsNone(result.backup_path)
        self.assertFalse(result.replaced)
        self.assertGreater(result.bytes_written, 0)
        self.assertTrue(target_path.exists())

        loaded_meta, val = load_metadata(target_path)
        self.assertTrue(val.is_valid)
        self.assertTrue(val.is_supported)
        self.assertEqual(len(loaded_meta.samples), 1)
        self.assertEqual(loaded_meta.samples[0]["sample_id"], "00001")

    def test_write_metadata_atomic_replace_with_backup(self):
        target_path = self.test_dir / "faceset_metadata.v1.json"

        # 1. Initial write
        meta1 = FacesetMetadataV1(samples=[{"sample_id": "01", "sample_key": "k1", "signature": "s1"}])
        write_metadata_atomic(target_path, meta1, keep_backup=True)

        # 2. Overwrite
        meta2 = FacesetMetadataV1(samples=[{"sample_id": "02", "sample_key": "k2", "signature": "s2"}])
        res2 = write_metadata_atomic(target_path, meta2, keep_backup=True)

        self.assertTrue(res2.replaced)
        self.assertIsNotNone(res2.backup_path)
        backup_file = target_path.with_suffix(target_path.suffix + ".bak")
        self.assertEqual(res2.backup_path, backup_file.resolve())
        self.assertTrue(backup_file.exists())

        # Verify target has meta2
        loaded_target, _ = load_metadata(target_path)
        self.assertEqual(loaded_target.samples[0]["sample_id"], "02")

        # Verify backup has meta1
        loaded_bak, _ = load_metadata(backup_file)
        self.assertEqual(loaded_bak.samples[0]["sample_id"], "01")

    def test_atomic_write_failure_preserves_target(self):
        target_path = self.test_dir / "faceset_metadata.v1.json"
        meta1 = FacesetMetadataV1(samples=[{"sample_id": "01", "sample_key": "k1", "signature": "s1"}])
        write_metadata_atomic(target_path, meta1, keep_backup=True)

        # Invalid metadata (unsupported schema version)
        invalid_meta = FacesetMetadataV1(schema_version=999, samples=[])

        with self.assertRaises(MetadataStoreError):
            write_metadata_atomic(target_path, invalid_meta)

        # Ensure target file still has original meta1
        loaded_target, val = load_metadata(target_path)
        self.assertTrue(val.is_valid)
        self.assertEqual(loaded_target.samples[0]["sample_id"], "01")

        # Ensure no temp file left
        temp_files = list(self.test_dir.glob(".*.tmp"))
        self.assertEqual(len(temp_files), 0)


if __name__ == "__main__":
    unittest.main()
