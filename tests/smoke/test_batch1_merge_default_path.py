"""Batch 1 Merge 默认路径 smoke。

目标：
- 验证 Enhancement Config 缺失或全部关闭时，Merge 仍走传统 MergeMasked 路径；
- 用 dummy predictor + 最小 fixture 覆盖 MergeMaskedFace 默认工程路径；
- macOS 无 cv2/tensorflow 时通过依赖 stub 完成结构级验证。

本文件不实现 Shape-aware Merge，也不修改 merger 算法逻辑。
"""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
MERGE_MASKED_PATH = REPO_ROOT / "merger" / "MergeMasked.py"
MERGER_CONFIG_PATH = REPO_ROOT / "merger" / "MergerConfig.py"
FACE_TYPE_PATH = REPO_ROOT / "facelib" / "FaceType.py"


def _load_module_from_path(module_name: str, path: Path, sys_modules=None):
    if sys_modules is None:
        sys_modules = {}
    with mock.patch.dict(sys.modules, sys_modules, clear=False):
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module


def _build_face_type_module():
    return _load_module_from_path(
        "batch1_merge_face_type",
        FACE_TYPE_PATH,
    )


class _FakeCv2:
    """足以跑通 MergeMaskedFace 默认 overlay 路径的最小 cv2 stub。"""

    INTER_CUBIC = 1
    INTER_LINEAR = 2
    WARP_INVERSE_MAP = 16
    MORPH_ELLIPSE = 2
    IMREAD_UNCHANGED = -1

    @staticmethod
    def resize(img, dsize, interpolation=None):
        img = np.asarray(img)
        width, height = int(dsize[0]), int(dsize[1])
        if img.ndim == 2:
            out = np.zeros((height, width), dtype=np.float32)
        else:
            channels = img.shape[2] if img.ndim == 3 else 1
            out = np.zeros((height, width, channels), dtype=np.float32)
            if img.ndim == 2:
                img = img[..., None]

        src_h = max(img.shape[0], 1)
        src_w = max(img.shape[1], 1)
        for y in range(height):
            sy = min(src_h - 1, int(y * src_h / height))
            for x in range(width):
                sx = min(src_w - 1, int(x * src_w / width))
                out[y, x] = img[sy, sx]
        return out.astype(np.float32, copy=False)

    @staticmethod
    def warpAffine(src, M, dsize, dst=None, flags=0, borderMode=None, borderValue=None):
        width, height = int(dsize[0]), int(dsize[1])
        src = np.asarray(src)
        if src.ndim == 3 and src.shape[2] == 1:
            src = src[..., 0]
        resized = _FakeCv2.resize(src, (width, height))
        if isinstance(dst, np.ndarray) and dst.size > 0:
            if dst.ndim == 2:
                if resized.ndim == 3:
                    resized = resized[..., 0]
                out = np.zeros((height, width), dtype=np.float32)
                out[...] = resized
                return out
            if dst.ndim == 3:
                if resized.ndim == 2:
                    resized = resized[..., None]
                channels = dst.shape[2]
                out = np.zeros((height, width, channels), dtype=np.float32)
                c = min(channels, resized.shape[2] if resized.ndim == 3 else 1)
                if resized.ndim == 2:
                    out[..., 0] = resized
                else:
                    out[..., :c] = resized[..., :c]
                return out
        return resized

    @staticmethod
    def getStructuringElement(shape, ksize):
        k = int(ksize[0]) if isinstance(ksize, (tuple, list)) else int(ksize)
        k = max(k, 1)
        return np.ones((k, k), dtype=np.uint8)

    @staticmethod
    def erode(src, kernel, iterations=1):
        return np.asarray(src, dtype=np.float32).copy()

    @staticmethod
    def dilate(src, kernel, iterations=1):
        return np.asarray(src, dtype=np.float32).copy()

    @staticmethod
    def GaussianBlur(src, ksize, sigmaX):
        return np.asarray(src, dtype=np.float32).copy()

    @staticmethod
    def medianBlur(src, ksize):
        return np.asarray(src).copy()

    @staticmethod
    def boundingRect(mask):
        ys, xs = np.where(np.asarray(mask) > 0)
        if len(xs) == 0:
            return (0, 0, 0, 0)
        x0, x1 = int(xs.min()), int(xs.max())
        y0, y1 = int(ys.min()), int(ys.max())
        return (x0, y0, x1 - x0 + 1, y1 - y0 + 1)

    @staticmethod
    def seamlessClone(src, dst, mask, p, flags):
        return np.asarray(dst).copy()


def _build_landmarks_processor_stub():
    mod = types.ModuleType("facelib.LandmarksProcessor")

    def get_image_hull_mask(image_shape, image_landmarks, eyebrows_expand_mod=1.0):
        h, w = image_shape[:2]
        yy, xx = np.mgrid[0:h, 0:w]
        cy, cx = h / 2.0, w / 2.0
        ry, rx = h * 0.28, w * 0.22
        mask = (((yy - cy) / ry) ** 2 + ((xx - cx) / rx) ** 2) <= 1.0
        return mask.astype(np.float32)

    def get_transform_mat(image_landmarks, output_size, face_type, scale=1.0):
        return np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)

    mod.get_image_hull_mask = get_image_hull_mask
    mod.get_transform_mat = get_transform_mat
    return mod


def _build_imagelib_stub():
    mod = types.ModuleType("core.imagelib")

    def normalize_channels(img, target_channels):
        img = np.asarray(img)
        if img.ndim == 2:
            img = img[..., None]
        c = img.shape[2]
        if c == target_channels:
            return img
        if c > target_channels:
            return img[..., :target_channels]
        pad = np.zeros(img.shape[:2] + (target_channels - c,), dtype=img.dtype)
        return np.concatenate([img, pad], axis=-1)

    def identity_color_transfer(src, *args, **kwargs):
        return np.asarray(src, dtype=np.float32).copy()

    mod.normalize_channels = normalize_channels
    mod.reinhard_color_transfer = identity_color_transfer
    mod.linear_color_transfer = identity_color_transfer
    mod.color_transfer_mkl = identity_color_transfer
    mod.color_transfer_idt = identity_color_transfer
    mod.color_transfer_sot = identity_color_transfer
    mod.color_transfer_mix = identity_color_transfer
    mod.color_hist_match = identity_color_transfer
    mod.reduce_colors = lambda img, n_colors: np.asarray(img, dtype=np.float32).copy()
    mod.blursharpen = lambda img, *a, **k: np.asarray(img, dtype=np.float32).copy()
    mod.LinearMotionBlur = lambda img, *a, **k: np.asarray(img, dtype=np.float32).copy()
    return mod


def _build_interact_stub():
    interact_pkg = types.ModuleType("core.interact")
    interact_mod = types.ModuleType("core.interact.interact")

    class _IO:
        def log_info(self, *args, **kwargs):
            return None

        def log_err(self, *args, **kwargs):
            return None

        def input_int(self, *args, **kwargs):
            return 0

        def input_bool(self, *args, **kwargs):
            return False

        def input_str(self, *args, **kwargs):
            return None

        def input_number(self, *args, **kwargs):
            return 0.0

    interact_mod.interact = _IO()
    interact_pkg.interact = interact_mod.interact
    return interact_pkg, interact_mod


def load_merger_config_module():
    face_type_mod = _build_face_type_module()
    facelib_mod = types.ModuleType("facelib")
    facelib_mod.FaceType = face_type_mod.FaceType

    interact_pkg, interact_mod = _build_interact_stub()
    core_mod = types.ModuleType("core")
    core_mod.interact = interact_pkg

    stubs = {
        "facelib": facelib_mod,
        "core": core_mod,
        "core.interact": interact_pkg,
        "core.interact.interact": interact_mod,
    }
    module = _load_module_from_path(
        "batch1_merge_merger_config",
        MERGER_CONFIG_PATH,
        sys_modules=stubs,
    )
    return module, face_type_mod.FaceType


def load_merge_masked_module():
    face_type_mod = _build_face_type_module()
    facelib_mod = types.ModuleType("facelib")
    facelib_mod.FaceType = face_type_mod.FaceType
    landmarks_mod = _build_landmarks_processor_stub()
    facelib_mod.LandmarksProcessor = landmarks_mod

    interact_pkg, interact_mod = _build_interact_stub()
    imagelib_mod = _build_imagelib_stub()

    core_mod = types.ModuleType("core")
    core_mod.imagelib = imagelib_mod
    core_mod.interact = interact_pkg

    cv2ex_mod = types.ModuleType("core.cv2ex")

    def cv2_imread(filename, flags=None, loader_func=None, verbose=True):
        raise AssertionError("MergeMaskedFace smoke 不应走到磁盘读图路径")

    def cv2_imwrite(*args, **kwargs):
        return True

    def cv2_resize(x, *args, **kwargs):
        return _FakeCv2.resize(x, args[0] if args else kwargs.get("dsize"))

    cv2ex_mod.cv2_imread = cv2_imread
    cv2ex_mod.cv2_imwrite = cv2_imwrite
    cv2ex_mod.cv2_resize = cv2_resize

    stubs = {
        "cv2": _FakeCv2,
        "facelib": facelib_mod,
        "facelib.LandmarksProcessor": landmarks_mod,
        "core": core_mod,
        "core.imagelib": imagelib_mod,
        "core.interact": interact_pkg,
        "core.interact.interact": interact_mod,
        "core.cv2ex": cv2ex_mod,
    }
    module = _load_module_from_path(
        "batch1_merge_merge_masked",
        MERGE_MASKED_PATH,
        sys_modules=stubs,
    )
    return module, face_type_mod.FaceType


def make_dummy_predictor(predictor_input_shape):
    """返回与输入同分布的 face + 两个有效 mask，覆盖传统三输出 predictor 协议。"""

    h, w = predictor_input_shape[0], predictor_input_shape[1]

    def predictor_func(face_bgr):
        face = np.asarray(face_bgr, dtype=np.float32)
        if face.shape[0] != h or face.shape[1] != w:
            face = np.resize(face, (h, w, 3)).astype(np.float32)
        yy, xx = np.mgrid[0:h, 0:w]
        cy, cx = (h - 1) / 2.0, (w - 1) / 2.0
        ry, rx = h * 0.35, w * 0.30
        mask = ((((yy - cy) / max(ry, 1e-6)) ** 2) + (((xx - cx) / max(rx, 1e-6)) ** 2) <= 1.0)
        # 必须返回 HxW 二维 mask：MergeMasked 会对 mask 做 np.pad(input_size)，
        # 若传入 HxWx1，pad 会把 channel 维也扩开，导致后续广播失败。
        mask_f = mask.astype(np.float32)
        prd_face = np.clip(face * 0.85 + 0.05, 0.0, 1.0)
        prd_src_mask = mask_f
        prd_dst_mask = np.clip(mask_f * 0.9 + 0.05, 0.0, 1.0)
        return prd_face, prd_src_mask, prd_dst_mask

    return predictor_func


def make_default_masked_cfg(merger_config_module, FaceType, **overrides):
    cfg = merger_config_module.MergerConfigMasked(
        face_type=FaceType.FULL,
        default_mode="overlay",
        mode="overlay",
        mask_mode=4,
        super_resolution_power=0,
        color_transfer_mode=0,
        erode_mask_modifier=0,
        blur_mask_modifier=0,
        motion_blur_power=0,
        output_face_scale=0,
        image_denoise_power=0,
        bicubic_degrade_power=0,
        color_degrade_power=0,
        sharpen_mode=0,
        blursharpen_amount=0,
    )
    for key, value in overrides.items():
        setattr(cfg, key, value)
    return cfg


def make_synthetic_frame(height=96, width=80):
    img = np.zeros((height, width, 3), dtype=np.float32)
    ys = np.linspace(0.1, 0.7, height, dtype=np.float32)[:, None]
    xs = np.linspace(0.2, 0.9, width, dtype=np.float32)[None, :]
    img[..., 0] = ys
    img[..., 1] = xs
    img[..., 2] = 0.4
    cy, cx = height // 2, width // 2
    img[cy - 18 : cy + 18, cx - 14 : cx + 14, :] = 0.65
    img_u8 = np.clip(img * 255.0, 0, 255).astype(np.uint8)
    return img_u8, img


def make_landmarks(height=96, width=80):
    """固定 68 点 fixture，围绕画面中心。"""
    cx, cy = width / 2.0, height / 2.0
    pts = []
    for i in range(17):
        t = i / 16.0
        pts.append([cx - 22 + 44 * t, cy + 20 + 8 * abs(t - 0.5)])
    while len(pts) < 68:
        idx = len(pts)
        ang = (idx / 68.0) * 2.0 * np.pi
        pts.append([cx + 12.0 * np.cos(ang), cy + 16.0 * np.sin(ang)])
    return np.asarray(pts[:68], dtype=np.float32)


def assert_image_mask_contract(test_case, out_img, out_mask, expected_hw):
    test_case.assertEqual(out_img.shape, (expected_hw[0], expected_hw[1], 3))
    test_case.assertTrue(out_mask.ndim in (2, 3))
    test_case.assertEqual(out_mask.shape[0], expected_hw[0])
    test_case.assertEqual(out_mask.shape[1], expected_hw[1])
    test_case.assertEqual(out_img.dtype, np.float32)
    test_case.assertTrue(np.issubdtype(out_mask.dtype, np.floating))
    test_case.assertTrue(np.isfinite(out_img).all())
    test_case.assertTrue(np.isfinite(out_mask).all())
    test_case.assertGreaterEqual(float(out_img.min()), 0.0)
    test_case.assertLessEqual(float(out_img.max()), 1.0)
    test_case.assertGreaterEqual(float(out_mask.min()), 0.0)
    test_case.assertLessEqual(float(out_mask.max()), 1.0)


class Batch1MergeDefaultPathSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.merger_config_module, cls.FaceType = load_merger_config_module()
        cls.merge_masked_module, _ = load_merge_masked_module()
        from core.enhancements import normalize_enhancement_config as _normalize

        cls._normalize_enhancement_config = staticmethod(_normalize)

    def test_enhancement_config_missing_keeps_merge_disabled(self):
        legacy_options = {
            "resolution": 128,
            "face_type": "f",
        }
        cfg = self._normalize_enhancement_config(legacy_options.get("enhancements"))
        self.assertFalse(cfg.merge_enabled)
        self.assertFalse(cfg.is_enabled("merge"))
        self.assertFalse(cfg.is_enabled("merge.shape_aware_warp"))
        self.assertFalse(cfg.is_enabled("merge.shape_aware_mask"))
        self.assertFalse(cfg.is_enabled("merge.source_shape_template"))
        self.assertFalse(cfg.is_enabled("merge.temporal_stabilization"))

    def test_explicit_disabled_enhancement_config_matches_missing(self):
        missing = self._normalize_enhancement_config(None)
        disabled = self._normalize_enhancement_config(
            {
                "schema_version": 1,
                "merge": {
                    "enabled": False,
                    "shape_aware_warp": True,
                    "shape_aware_mask": True,
                },
            }
        )
        self.assertEqual(missing.merge_enabled, disabled.merge_enabled)
        self.assertEqual(
            missing.is_enabled("merge.shape_aware_warp"),
            disabled.is_enabled("merge.shape_aware_warp"),
        )
        self.assertFalse(disabled.is_enabled("merge.shape_aware_warp"))

    def test_merger_config_masked_defaults_do_not_require_enhancements(self):
        cfg = make_default_masked_cfg(self.merger_config_module, self.FaceType)
        self.assertEqual("overlay", cfg.mode)
        self.assertEqual(0, cfg.super_resolution_power)
        self.assertFalse(hasattr(cfg, "enhancements"))
        self.assertNotIn("shape_aware_warp", cfg.__dict__)
        self.assertNotIn("source_shape_template", cfg.__dict__)

    def test_merge_masked_face_overlay_with_dummy_predictor(self):
        height, width = 96, 80
        predictor_input_shape = (64, 64, 3)
        img_u8, img_f = make_synthetic_frame(height, width)
        landmarks = make_landmarks(height, width)
        cfg = make_default_masked_cfg(self.merger_config_module, self.FaceType)
        frame_info = SimpleNamespace(filepath="synthetic.png", landmarks_list=[landmarks], motion_deg=0, motion_power=0)

        predictor_func = make_dummy_predictor(predictor_input_shape)

        def face_enhancer_func(*args, **kwargs):
            raise AssertionError("默认路径不应调用 face enhancer")

        def xseg_func(*args, **kwargs):
            raise AssertionError("默认路径不应调用 xseg extractor")

        out_img, out_mask = self.merge_masked_module.MergeMaskedFace(
            predictor_func,
            predictor_input_shape,
            face_enhancer_func,
            xseg_func,
            cfg,
            frame_info,
            img_u8,
            img_f,
            landmarks,
        )

        assert_image_mask_contract(self, out_img, out_mask, (height, width))
        self.assertGreater(float(np.asarray(out_mask).max()), 0.0)

    def test_merge_masked_face_original_mode(self):
        height, width = 96, 80
        predictor_input_shape = (64, 64, 3)
        img_u8, img_f = make_synthetic_frame(height, width)
        landmarks = make_landmarks(height, width)
        cfg = make_default_masked_cfg(
            self.merger_config_module,
            self.FaceType,
            mode="original",
        )
        frame_info = SimpleNamespace(filepath="synthetic.png", landmarks_list=[landmarks], motion_deg=0, motion_power=0)
        predictor_func = make_dummy_predictor(predictor_input_shape)

        out_img, out_mask = self.merge_masked_module.MergeMaskedFace(
            predictor_func,
            predictor_input_shape,
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("no enhancer")),
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("no xseg")),
            cfg,
            frame_info,
            img_u8,
            img_f,
            landmarks,
        )

        assert_image_mask_contract(self, out_img, out_mask, (height, width))
        np.testing.assert_allclose(out_img, img_f, rtol=0.0, atol=1e-6)

    def test_missing_and_disabled_enhancement_do_not_change_merge_output(self):
        """Batch 1 尚未把 enhancement 接入 MergeMasked 时，传统路径输出应与配置缺失一致。"""
        height, width = 96, 80
        predictor_input_shape = (64, 64, 3)
        img_u8, img_f = make_synthetic_frame(height, width)
        landmarks = make_landmarks(height, width)
        frame_info = SimpleNamespace(filepath="synthetic.png", landmarks_list=[landmarks], motion_deg=0, motion_power=0)
        predictor_func = make_dummy_predictor(predictor_input_shape)

        cfg_a = make_default_masked_cfg(self.merger_config_module, self.FaceType)
        cfg_b = make_default_masked_cfg(self.merger_config_module, self.FaceType)

        enh_missing = self._normalize_enhancement_config(None)
        enh_disabled = self._normalize_enhancement_config({"merge": {"enabled": False}})
        self.assertFalse(enh_missing.merge_enabled)
        self.assertFalse(enh_disabled.merge_enabled)

        def run(cfg):
            return self.merge_masked_module.MergeMaskedFace(
                predictor_func,
                predictor_input_shape,
                lambda *a, **k: (_ for _ in ()).throw(AssertionError("no enhancer")),
                lambda *a, **k: (_ for _ in ()).throw(AssertionError("no xseg")),
                cfg,
                frame_info,
                img_u8.copy(),
                img_f.copy(),
                landmarks.copy(),
            )

        out_img_a, out_mask_a = run(cfg_a)
        out_img_b, out_mask_b = run(cfg_b)

        np.testing.assert_allclose(out_img_a, out_img_b, rtol=0.0, atol=0.0)
        np.testing.assert_allclose(out_mask_a, out_mask_b, rtol=0.0, atol=0.0)
        assert_image_mask_contract(self, out_img_a, out_mask_a, (height, width))

    def test_dummy_predictor_protocol_is_three_outputs(self):
        predictor = make_dummy_predictor((32, 32, 3))
        face = np.full((32, 32, 3), 0.3, dtype=np.float32)
        prd_face, prd_src_mask, prd_dst_mask = predictor(face)
        self.assertEqual(prd_face.shape, (32, 32, 3))
        self.assertEqual(prd_src_mask.shape, (32, 32))
        self.assertEqual(prd_dst_mask.shape, (32, 32))
        self.assertTrue(np.isfinite(prd_face).all())
        self.assertGreaterEqual(float(prd_src_mask.min()), 0.0)
        self.assertLessEqual(float(prd_src_mask.max()), 1.0)


if __name__ == "__main__":
    unittest.main()
