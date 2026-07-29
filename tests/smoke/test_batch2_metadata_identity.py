import sys
import unittest
from pathlib import Path

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from samplelib.metadata.identity import (
    build_sample_id,
    build_sample_key,
    normalize_sample_path,
)


class TestBatch2MetadataIdentity(unittest.TestCase):
    def test_normalize_sample_path_valid(self):
        """Test normalization for clean relative paths."""
        self.assertEqual(normalize_sample_path("00001.jpg"), "00001.jpg")
        self.assertEqual(normalize_sample_path("./00001.jpg"), "00001.jpg")
        self.assertEqual(normalize_sample_path("personA/00001.jpg"), "personA/00001.jpg")
        self.assertEqual(normalize_sample_path("personA\\sub\\00001.jpg"), "personA/sub/00001.jpg")

    def test_normalize_sample_path_preserves_casing(self):
        """Verify casing is preserved for canonical sample keys."""
        self.assertEqual(normalize_sample_path("PersonA/Frame_001.JPG"), "PersonA/Frame_001.JPG")

    def test_normalize_sample_path_rejects_illegal(self):
        """Verify absolute paths and directory traversal are rejected."""
        with self.assertRaises(ValueError):
            normalize_sample_path("/absolute/path/00001.jpg")

        with self.assertRaises(ValueError):
            normalize_sample_path("C:\\Windows\\00001.jpg")

        with self.assertRaises(ValueError):
            normalize_sample_path("personA/../00001.jpg")

    def test_build_sample_key_ordinary_person_packed(self):
        """Verify build_sample_key produces expected relative keys for all faceset types."""
        # Ordinary
        key1 = build_sample_key("00001.jpg")
        self.assertEqual(key1, "00001.jpg")

        # Person faceset with separate person_name
        key2 = build_sample_key("00001.jpg", person_name="person_10")
        self.assertEqual(key2, "person_10/00001.jpg")

        # Windows backslash input
        key3 = build_sample_key("person_10\\00001.jpg")
        self.assertEqual(key3, "person_10/00001.jpg")

    def test_build_sample_id_stability(self):
        """Verify build_sample_id is deterministic and stable across calls."""
        key = "personA/00001.jpg"
        id1 = build_sample_id(key)
        id2 = build_sample_id(key)
        self.assertEqual(id1, id2)
        self.assertEqual(len(id1), 32)

        # Different keys yield different IDs
        different_id = build_sample_id("personA/00002.jpg")
        self.assertNotEqual(id1, different_id)


if __name__ == "__main__":
    unittest.main()
