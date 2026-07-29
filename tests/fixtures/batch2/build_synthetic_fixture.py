import os
import shutil
import sys
import unittest.mock as mock
from pathlib import Path

import cv2
import numpy as np

from core.cv2ex import cv2_imwrite
from DFLIMG import DFLIMG, DFLJPG
from facelib import FaceType
from samplelib.PackedFaceset import PackedFaceset, packed_faceset_filename


def generate_synthetic_landmarks(pose_type="center"):
    """
    Generate 68 landmark coordinates (2D) for synthetic aligned face images.
    Default shape: 256x256 image coordinates.
    Produces realistic perspective distortion for solvePnP pose estimation.
    """
    landmarks = np.zeros((68, 2), dtype=np.float32)
    center_x, center_y = 128.0, 128.0

    # Jaw line 0-16
    for i in range(17):
        landmarks[i] = [center_x - 80 + i * 10, center_y + 40 + abs(i - 8) * 3]

    # Eyebrows 17-26
    for i in range(5):
        landmarks[17 + i] = [center_x - 60 + i * 10, center_y - 30]
        landmarks[22 + i] = [center_x + 20 + i * 10, center_y - 30]

    # Nose 27-35
    for i in range(9):
        landmarks[27 + i] = [center_x - 10 + (i % 3) * 10, center_y - 10 + (i // 3) * 15]

    # Eyes 36-47
    for i in range(6):
        landmarks[36 + i] = [center_x - 50 + (i % 3) * 10, center_y - 15 + (i // 3) * 5]
        landmarks[42 + i] = [center_x + 20 + (i % 3) * 10, center_y - 15 + (i // 3) * 5]

    # Mouth 48-67
    for i in range(20):
        landmarks[48 + i] = [center_x - 30 + (i % 5) * 12, center_y + 30 + (i // 5) * 8]

    if pose_type in ("left_yaw", "minor_left"):
        landmarks[27:36, 0] -= 18.0  # Nose
        landmarks[36:42, 0] -= 10.0  # Left eye
        landmarks[42:48, 0] -= 22.0  # Right eye
        landmarks[0:17, 0] -= 12.0   # Jaw
    elif pose_type in ("right_yaw", "minor_right"):
        landmarks[27:36, 0] += 18.0  # Nose
        landmarks[36:42, 0] += 22.0  # Left eye
        landmarks[42:48, 0] += 10.0  # Right eye
        landmarks[0:17, 0] += 12.0   # Jaw

    return landmarks



def generate_synthetic_image(img_type="clear", size=(256, 256, 3)):
    """
    Generate synthetic image data (RGB) without real human faces.
    """
    h, w, c = size
    img = np.zeros((h, w, c), dtype=np.uint8)

    if img_type == "clear":
        # Draw background and geometric shapes
        img[:, :] = (120, 140, 160)
        cv2.circle(img, (w // 2, h // 2), 60, (200, 220, 240), -1)  # Synthetic face oval
        cv2.circle(img, (w // 2 - 25, h // 2 - 20), 10, (40, 40, 40), -1)  # Left eye
        cv2.circle(img, (w // 2 + 25, h // 2 - 20), 10, (40, 40, 40), -1)  # Right eye
        cv2.ellipse(img, (w // 2, h // 2 + 25), (20, 10), 0, 0, 180, (40, 40, 180), 3)  # Mouth
    elif img_type == "blur":
        img = generate_synthetic_image("clear", size)
        img = cv2.GaussianBlur(img, (31, 31), 10)
    elif img_type == "dark":
        img[:, :] = (10, 10, 10)
    elif img_type == "bright":
        img[:, :] = (245, 245, 245)
    elif img_type == "black":
        img[:, :] = 0
    elif img_type == "white":
        img[:, :] = 255
    else:
        # Default gradient fill
        for y in range(h):
            img[y, :, 0] = int(y / h * 255)
            img[y, :, 1] = int(y / h * 200)
            img[y, :, 2] = 150

    return img


def create_dflimg_file(filepath, img_type="clear", pose_type="center", face_type=FaceType.FULL, source_filename="frame_0001.png"):
    """
    Create a valid DFLIMG aligned JPG file with embedded metadata and 68 landmarks.
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    img = generate_synthetic_image(img_type)
    cv2_imwrite(str(filepath), img)

    # Load and embed DFLJPG metadata
    dfl = DFLJPG.load(str(filepath))
    if dfl is None:
        raise RuntimeError(f"Failed to load DFLJPG after writing base image: {filepath}")

    landmarks = generate_synthetic_landmarks(pose_type)
    dfl_dict = {
        'face_type': FaceType.toString(face_type),
        'shape': img.shape,
        'landmarks': landmarks,
        'eyebrows_expand_mod': 1.0,
        'source_filename': source_filename,
        'source_rect': [10, 10, 200, 200],
        'source_landmarks': landmarks,
        'image_to_face_mat': np.eye(3, 3, dtype=np.float32),
    }

    dfl.set_dict(dfl_dict)
    dfl.save()
    return filepath


def build_ordinary_fixture(target_dir):
    """
    Build a set of ordinary aligned synthetic DFLIMG files in target_dir.
    """
    target_dir = Path(target_dir)
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    created_files = []
    configs = [
        ("00001_center.jpg", "clear", "center", FaceType.FULL, "frame_001.png"),
        ("00002_left.jpg", "clear", "minor_left", FaceType.FULL, "frame_002.png"),
        ("00003_right.jpg", "clear", "minor_right", FaceType.FULL, "frame_003.png"),
        ("00004_blur.jpg", "blur", "center", FaceType.FULL, "frame_004.png"),
        ("00005_中文文件名_dark.jpg", "dark", "minor_left", FaceType.FULL, "frame_005.png"),
        ("00006_bright.jpg", "bright", "center", FaceType.FULL, "frame_006.png"),
        ("00007_black.jpg", "black", "center", FaceType.FULL, "frame_007.png"),
        ("00008_white.jpg", "white", "center", FaceType.FULL, "frame_008.png"),
        ("00009_wf.jpg", "clear", "center", FaceType.WHOLE_FACE, "frame_009.png"),
        ("00010_head.jpg", "clear", "minor_right", FaceType.HEAD, "frame_010.png"),
    ]

    for fname, img_t, pose_t, face_t, src_f in configs:
        fp = target_dir / fname
        create_dflimg_file(fp, img_type=img_t, pose_type=pose_t, face_type=face_t, source_filename=src_f)
        created_files.append(fp)


    # Also add a corrupted file for bad file testing
    corrupt_fp = target_dir / "00011_corrupt.jpg"
    with open(corrupt_fp, "wb") as f:
        f.write(b"CORRUPTED_JPG_DATA_NOT_VALID")

    return created_files


def build_packed_fixture(ordinary_dir, pak_output_dir):
    """
    Build a packed faceset fixture using PackedFaceset.pack on ordinary_dir.
    """
    ordinary_dir = Path(ordinary_dir)
    pak_output_dir = Path(pak_output_dir)
    pak_output_dir.mkdir(parents=True, exist_ok=True)

    # Copy non-corrupt images to a temporary directory to build clean pack
    clean_dir = pak_output_dir / "clean_temp"
    if clean_dir.exists():
        shutil.rmtree(clean_dir)
    clean_dir.mkdir(parents=True, exist_ok=True)

    for f in ordinary_dir.glob("*.jpg"):
        if "corrupt" not in f.name:
            shutil.copy(f, clean_dir / f.name)

    pak_file = clean_dir / packed_faceset_filename
    if pak_file.exists():
        pak_file.unlink()

    from core.interact import interact as io

    # Mock interactive inputs during automated pack
    with mock.patch.object(io, "input", return_value=""), \
         mock.patch.object(io, "input_bool", return_value=False):
        PackedFaceset.pack(clean_dir)


    target_pak = pak_output_dir / packed_faceset_filename
    if target_pak.exists():
        target_pak.unlink()

    shutil.move(str(pak_file), str(target_pak))
    shutil.rmtree(clean_dir)
    return target_pak
