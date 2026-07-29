import os
import sys
import unittest
import tempfile
import numpy as np
from pathlib import Path

from core import pathex
from core.cv2ex import cv2_imread, cv2_imwrite
from core.interact import interact as io


class ChinesePathCompatibilityTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir_obj = tempfile.TemporaryDirectory(prefix="中文路径测试_")
        self.chinese_dir = Path(self.tmp_dir_obj.name)

    def tearDown(self):
        try:
            self.tmp_dir_obj.cleanup()
        except Exception:
            pass

    def test_cv2_imread_imwrite_chinese_path(self):
        # Create a dummy image
        img = np.zeros((64, 64, 3), dtype=np.uint8)
        img[10:50, 10:50] = [255, 128, 64]

        chinese_file = self.chinese_dir / "测试图片_0001.png"
        cv2_imwrite(chinese_file, img)

        self.assertTrue(chinese_file.exists(), "Image file with Chinese filename should be created.")

        loaded_img = cv2_imread(chinese_file)
        self.assertIsNotNone(loaded_img, "cv2_imread should successfully load image from Chinese path.")
        self.assertEqual(img.shape, loaded_img.shape)
        np.testing.assert_array_equal(img, loaded_img)

    def test_pathex_get_image_paths_chinese_dir(self):
        img = np.zeros((32, 32, 3), dtype=np.uint8)
        img_path = self.chinese_dir / "人脸_0001.jpg"
        cv2_imwrite(img_path, img)

        paths = pathex.get_image_paths(self.chinese_dir)
        self.assertEqual(len(paths), 1)
        self.assertEqual(Path(paths[0]).resolve(), img_path.resolve())

    def test_headless_show_image_chinese_path(self):
        import sys
        import core.interact.interact
        interact_mod = sys.modules['core.interact.interact']
        
        # Test Headless Mode preview saving with non-ASCII window name
        orig_headless = interact_mod._HEADLESS_MODE
        orig_dir = interact_mod._headless_preview_dir
        try:
            interact_mod._HEADLESS_MODE = True
            preview_dir = self.chinese_dir / "预览输出"
            preview_dir.mkdir(exist_ok=True)
            interact_mod._headless_preview_dir = str(preview_dir)

            test_img = np.ones((100, 100, 3), dtype=np.uint8) * 200
            io.named_window("Training preview_中文窗口")
            io.show_image("Training preview_中文窗口", test_img)

            saved_files = list(preview_dir.glob("*.png"))
            self.assertGreater(len(saved_files), 0, "Headless preview image should be saved in Chinese directory.")
        finally:
            interact_mod._HEADLESS_MODE = orig_headless
            interact_mod._headless_preview_dir = orig_dir




if __name__ == "__main__":
    unittest.main()
