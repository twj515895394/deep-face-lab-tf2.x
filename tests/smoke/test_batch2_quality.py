import sys
import unittest
from pathlib import Path

import numpy as np

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from samplelib.metadata.quality import (
    FacesetQualityConfig,
    compute_raw_quality,
    finalize_quality_scores,
    validate_image,
)
from tests.fixtures.batch2.build_synthetic_fixture import generate_synthetic_image


class TestBatch2Quality(unittest.TestCase):
    def test_validate_image_valid_and_invalid(self):
        """Test BGR image array validation."""
        clean_img = generate_synthetic_image("clear")
        val1 = validate_image(clean_img)
        self.assertTrue(val1.valid)

        # None / missing
        self.assertFalse(validate_image(None).valid)

        # 2D instead of 3D
        self.assertFalse(validate_image(np.zeros((100, 100), dtype=np.uint8)).valid)

        # Non-finite pixels
        nan_img = clean_img.astype(np.float32)
        nan_img[0, 0, 0] = np.nan
        self.assertFalse(validate_image(nan_img).valid)

    def test_compute_raw_quality_clear_vs_blur(self):
        """Verify raw sharpness of clear image is strictly higher than blurred image."""
        clear_img = generate_synthetic_image("clear")
        blur_img = generate_synthetic_image("blur")

        raw_clear = compute_raw_quality(clear_img)
        raw_blur = compute_raw_quality(blur_img)

        self.assertTrue(raw_clear.valid)
        self.assertTrue(raw_blur.valid)
        self.assertGreater(raw_clear.sharpness_raw, raw_blur.sharpness_raw)

    def test_finalize_quality_scores_percentile_normalization(self):
        """Verify Pass 2 percentile normalization and neutral fallback handling."""
        clear_img = generate_synthetic_image("clear")
        blur_img = generate_synthetic_image("blur")

        raw1 = compute_raw_quality(clear_img)
        raw2 = compute_raw_quality(blur_img)

        records = [
            {"sample_key": "img1.jpg", "quality_raw": raw1.__dict__},
            {"sample_key": "img2.jpg", "quality_raw": raw2.__dict__},
        ]

        finalized, norm_summary = finalize_quality_scores(records)
        self.assertEqual(len(finalized), 2)
        self.assertIn("p05_log_sharpness", norm_summary)

        score1 = finalized[0]["quality"]["quality_score"]
        score2 = finalized[1]["quality"]["quality_score"]
        self.assertGreater(score1, score2, "Clear image quality_score must be higher than blurred image score")

    def test_neutral_quality_when_all_identical(self):
        """Verify fallback neutral score (0.5) when all images have identical sharpness."""
        clear_img = generate_synthetic_image("clear")
        raw = compute_raw_quality(clear_img)

        records = [
            {"sample_key": "img1.jpg", "quality_raw": raw.__dict__},
            {"sample_key": "img2.jpg", "quality_raw": raw.__dict__},
        ]

        finalized, _ = finalize_quality_scores(records)
        self.assertEqual(finalized[0]["quality"]["sharpness_normalized"], 0.5)


if __name__ == "__main__":
    unittest.main()
