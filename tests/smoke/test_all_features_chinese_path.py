import os
import sys
import unittest
import tempfile
import numpy as np
from pathlib import Path

from core import pathex
from core.cv2ex import cv2_imread, cv2_imwrite
from core.interact import interact as io
from mainscripts import Sorter, Util, FacesetResizer, XSegUtil



class AllFeaturesChinesePathTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir_obj = tempfile.TemporaryDirectory(prefix="全功能中文路径测试_")
        self.chinese_root = Path(self.tmp_dir_obj.name)

    def tearDown(self):
        try:
            self.tmp_dir_obj.cleanup()
        except Exception:
            pass

    def test_sorter_chinese_path(self):
        input_dir = self.chinese_root / "排序输入_人脸"
        input_dir.mkdir(parents=True, exist_ok=True)

        for i in range(3):
            img = np.zeros((64, 64, 3), dtype=np.uint8)
            img[10:30, 10:30] = [i * 50, 100, 200]
            cv2_imwrite(input_dir / f"脸图_{i:04d}.png", img)

        paths = pathex.get_image_paths(input_dir)
        self.assertEqual(len(paths), 3)

        # Verify Sorter on Chinese path
        try:
            Sorter.main(input_path=input_dir, sort_by_method="origname")
        except Exception as e:
            self.fail(f"Sorter.main failed on Chinese path: {e}")

    def test_util_metadata_chinese_path(self):
        input_dir = self.chinese_root / "元数据测试_人脸"
        input_dir.mkdir(parents=True, exist_ok=True)

        img = np.zeros((64, 64, 3), dtype=np.uint8)
        cv2_imwrite(input_dir / "人脸_0001.jpg", img)

        meta_file = input_dir / "meta.dat"
        self.assertFalse(meta_file.exists())

        # Test save_faceset_metadata_folder
        try:
            Util.save_faceset_metadata_folder(input_dir)
        except Exception as e:
            self.fail(f"save_faceset_metadata_folder failed on Chinese path: {e}")

        self.assertTrue(meta_file.exists(), "meta.dat should be created.")

    def test_faceset_resizer_chinese_path(self):
        input_dir = self.chinese_root / "缩放测试_人脸"
        input_dir.mkdir(parents=True, exist_ok=True)

        img = np.zeros((128, 128, 3), dtype=np.uint8)
        cv2_imwrite(input_dir / "高清脸图_001.jpg", img)

        from unittest.mock import patch
        with patch.object(io, 'input_int', return_value=256), \
             patch.object(io, 'input_str', return_value='same'), \
             patch.object(io, 'input_bool', return_value=False):
            try:
                FacesetResizer.process_folder(input_dir)
            except Exception as e:
                self.fail(f"FacesetResizer.process_folder failed on Chinese path: {e}")


    def test_xseg_util_chinese_path(self):
        input_dir = self.chinese_root / "遮罩测试_人脸"
        input_dir.mkdir(parents=True, exist_ok=True)

        img = np.zeros((64, 64, 3), dtype=np.uint8)
        cv2_imwrite(input_dir / "人脸遮罩_001.jpg", img)

        from unittest.mock import patch
        with patch.object(io, 'input_str', return_value=''):
            # Test XSegUtil.remove_xseg
            try:
                XSegUtil.remove_xseg(input_dir)
            except Exception as e:
                self.fail(f"XSegUtil.remove_xseg failed on Chinese path: {e}")



if __name__ == "__main__":
    unittest.main()
