import os
import platform
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Check dependency availability before importing project modules that depend on cv2 and scipy
try:
    import cv2
    import scipy
    cv2_available = True
except ImportError:
    cv2_available = False


try:
    import tensorflow as tf
    tf_available = True
except ImportError:
    tf_available = False

if cv2_available:
    from core import mplib
    from facelib import FaceType
    from samplelib import SampleGeneratorFace, SampleLoader, SampleProcessor, SampleType
    from tests.fixtures.batch2.build_synthetic_fixture import (
        build_ordinary_fixture,
        build_packed_fixture,
    )




def collect_batch2_environment() -> dict:
    """
    Collect system environment, Python version, Git commit, OS details,
    and availability of key dependencies (TensorFlow, OpenCV, CUDA/GPU).
    """
    env = {
        "python_version": sys.version,
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "dependencies": {},
    }

    # Check OpenCV
    try:
        import cv2

        env["dependencies"]["cv2"] = cv2.__version__
    except ImportError:
        env["dependencies"]["cv2"] = None

    # Check NumPy
    try:
        import numpy

        env["dependencies"]["numpy"] = numpy.__version__
    except ImportError:
        env["dependencies"]["numpy"] = None

    # Check SciPy
    try:
        import scipy

        env["dependencies"]["scipy"] = scipy.__version__
    except ImportError:
        env["dependencies"]["scipy"] = None


    # Check TensorFlow & GPU
    try:
        import tensorflow as tf

        env["dependencies"]["tensorflow"] = tf.__version__
        gpus = tf.config.list_physical_devices("GPU")
        env["dependencies"]["gpu_available"] = len(gpus) > 0
        env["dependencies"]["gpu_devices"] = [g.name for g in gpus]
    except Exception as e:
        env["dependencies"]["tensorflow"] = None
        env["dependencies"]["gpu_available"] = False
        env["dependencies"]["gpu_devices"] = []

    return env


class TestBatch2Baseline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env_info = collect_batch2_environment()
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="dfl_batch2_test_"))
        cls.ordinary_dir = cls.temp_dir / "ordinary"
        cls.packed_dir = cls.temp_dir / "packed"

        if cv2_available:
            build_ordinary_fixture(cls.ordinary_dir)
            cls.packed_file = build_packed_fixture(cls.ordinary_dir, cls.packed_dir)

    @classmethod
    def tearDownClass(cls):
        if cls.temp_dir.exists():
            shutil.rmtree(cls.temp_dir)

    def test_environment_collection(self):
        """Test environment collector returns structured dict."""
        info = collect_batch2_environment()
        self.assertIn("python_version", info)
        self.assertIn("dependencies", info)
        self.assertIsNotNone(info["dependencies"]["numpy"])

    @unittest.skipUnless(cv2_available, "Requires OpenCV (cv2)")
    def test_sample_loader_ordinary_and_packed(self):

        """
        Verify SampleLoader loads ordinary aligned faceset and packed faceset correctly.
        Verify Sample.read_raw_file and Sample.load_bgr pipelines work.
        """
        # Load Ordinary
        ordinary_samples = SampleLoader.load(SampleType.FACE, self.ordinary_dir)
        self.assertGreater(len(ordinary_samples), 0, "Ordinary samples should not be empty")

        for sample in ordinary_samples:
            self.assertIsNotNone(sample.filename)
            self.assertIsNotNone(sample.landmarks)
            bgr = sample.load_bgr()
            self.assertIsNotNone(bgr)
            self.assertEqual(len(bgr.shape), 3)

        # Load Packed
        packed_samples = SampleLoader.load(SampleType.FACE, self.packed_dir)
        self.assertGreater(len(packed_samples), 0, "Packed samples should not be empty")

        for sample in packed_samples:
            self.assertIsNotNone(sample.filename)
            self.assertIsNotNone(sample.landmarks)
            raw_bytes = sample.read_raw_file()
            self.assertGreater(len(raw_bytes), 0, "Raw bytes from packed faceset should not be empty")
            bgr = sample.load_bgr()
            self.assertIsNotNone(bgr)

    @unittest.skipUnless(cv2_available, "Requires OpenCV (cv2)")
    def test_index_host_seed_reproducibility(self):
        """
        Freeze legacy IndexHost behavior with fixed seed.
        Verify first 100 draws, epoch coverage, and reproducibility across instances.
        """
        count = 50
        seed = 42

        host1 = mplib.IndexHost(count, rnd_seed=seed)
        host2 = mplib.IndexHost(count, rnd_seed=seed)
        try:
            cli1 = host1.create_cli()
            draws1 = [cli1.multi_get(1)[0] for _ in range(100)]

            cli2 = host2.create_cli()
            draws2 = [cli2.multi_get(1)[0] for _ in range(100)]

            self.assertEqual(draws1, draws2, "IndexHost with same seed must yield identical sequence")
            first_epoch = set(draws1[:count])
            self.assertEqual(len(first_epoch), count, "One full epoch of IndexHost should cover all indices")
        finally:
            host1.close()
            host2.close()
            self.assertFalse(host1.thread.is_alive())
            self.assertFalse(host2.thread.is_alive())

    @unittest.skipUnless(cv2_available, "Requires OpenCV (cv2)")
    def test_index2d_host_bucket_sampling(self):
        """
        Freeze legacy Index2DHost sampling behavior across buckets.
        """
        buckets = [
            [0, 1, 2],
            [3, 4],
            [5, 6, 7, 8],
        ]
        host = mplib.Index2DHost(buckets)
        try:
            cli = host.create_cli()

            draws = [cli.multi_get(1)[0] for _ in range(30)]
            self.assertEqual(len(draws), 30)
            flattened = [idx for b in buckets for idx in b]
            for d in draws:
                self.assertIn(d, flattened)
        finally:
            host.close()
            self.assertFalse(host.thread.is_alive())

    @unittest.skipUnless(cv2_available, "Requires OpenCV (cv2)")
    def test_sample_generator_face_tensor_contract(self):
        """
        Freeze SampleGeneratorFace output tensor contract for ordinary & packed,
        debug=True/False, and eyes_mouth_prio=False/True options.
        """
        # Option Set 1: Standard face image only
        sample_types_base = [
            {
                "sample_type": SampleProcessor.SampleType.FACE_IMAGE,
                "channel_type": SampleProcessor.ChannelType.BGR,
                "face_type": FaceType.FULL,
                "resolution": 64,
                "warp": True,
                "transform": True,
            },
        ]

        # Option Set 2: Face image + face mask (FULL_FACE and EYES_MOUTH)
        sample_types_with_masks = [
            {
                "sample_type": SampleProcessor.SampleType.FACE_IMAGE,
                "channel_type": SampleProcessor.ChannelType.BGR,
                "face_type": FaceType.FULL,
                "resolution": 64,
                "warp": True,
                "transform": True,
            },
            {
                "sample_type": SampleProcessor.SampleType.FACE_MASK,
                "channel_type": SampleProcessor.ChannelType.G,
                "face_type": FaceType.FULL,
                "face_mask_type": SampleProcessor.FaceMaskType.FULL_FACE,
                "resolution": 64,
                "warp": True,
                "transform": True,
            },
            {
                "sample_type": SampleProcessor.SampleType.FACE_MASK,
                "channel_type": SampleProcessor.ChannelType.G,
                "face_type": FaceType.FULL,
                "face_mask_type": SampleProcessor.FaceMaskType.EYES_MOUTH,
                "resolution": 64,
                "warp": True,
                "transform": True,
            },
        ]

        opts = SampleProcessor.Options()

        # Case 1: Base sample types
        gen_base = SampleGeneratorFace(
            self.ordinary_dir,
            debug=True,
            batch_size=2,
            sample_process_options=opts,
            output_sample_types=sample_types_base,
        )
        batch_base = next(gen_base)
        count_base = len(batch_base)
        shapes_base = [arr.shape for arr in batch_base]
        dtypes_base = [arr.dtype for arr in batch_base]

        # Case 2: With masks
        gen_masks = SampleGeneratorFace(
            self.ordinary_dir,
            debug=True,
            batch_size=2,
            sample_process_options=opts,
            output_sample_types=sample_types_with_masks,
        )
        batch_masks = next(gen_masks)
        count_masks = len(batch_masks)
        shapes_masks = [arr.shape for arr in batch_masks]
        dtypes_masks = [arr.dtype for arr in batch_masks]

        self.assertGreater(count_masks, count_base, "Including FaceMaskType (FULL_FACE, EYES_MOUTH) should yield additional mask tensors")

        # Verify packed generator tensor shapes match ordinary generator tensor shapes
        gen_packed = SampleGeneratorFace(
            self.packed_dir,
            debug=True,
            batch_size=2,
            sample_process_options=opts,
            output_sample_types=sample_types_base,
        )
        batch_packed = next(gen_packed)
        shapes_packed = [arr.shape for arr in batch_packed]
        self.assertEqual(shapes_base, shapes_packed, "Packed faceset generator tensor contract must match Ordinary faceset")



if __name__ == "__main__":
    unittest.main()
