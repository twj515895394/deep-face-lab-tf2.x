import unittest
import json
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Ensure repository root is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Stub only packages that are truly missing. Never replace a real installed
# package (e.g. cv2) with MagicMock — that breaks subsequent fixture tests
# when this module is collected first in a multi-test run.
for mod_name in ['scipy', 'scipy.spatial', 'cv2', 'tensorflow', 'numexpr', 'h5py']:
    if mod_name in sys.modules:
        continue
    try:
        __import__(mod_name)
    except Exception:
        sys.modules[mod_name] = MagicMock()

from models.ModelBase import ModelBase

class TestOptionsJson(unittest.TestCase):
    def setUp(self):
        # Create a dummy ModelBase object without running full __init__
        self.model = ModelBase.__new__(ModelBase)
        self.model.options = {
            'batch_size': 4,
            'resolution': 128,
            'archi': 'df-hd',
            'random_warp': True,
            'lr_dropout': 'n'
        }
        self.model.iter = 100
        self.model.options_json = None

    def test_is_first_run(self):
        self.model.iter = 0
        self.assertTrue(self.model.is_first_run())
        self.model.iter = 100
        self.assertFalse(self.model.is_first_run())

    def test_json_parsing_data_types(self):
        test_json = json.dumps({
            "batch_size": 16,
            "target_iter": 500000,
            "gan_power": 0.1,
            "random_warp": "false",
            "masked_training": "true",
            "lr_dropout": True,
            "optimizer": "adabelief"
        })
        self.model.options_json = test_json
        
        with patch('models.ModelBase.io.log_info'):
            self.model.load_train_step_config()

        self.assertEqual(self.model.options['batch_size'], 16)
        self.assertEqual(self.model.options['target_iter'], 500000)
        self.assertEqual(self.model.options['gan_power'], 0.1)
        self.assertIs(self.model.options['random_warp'], False)
        self.assertIs(self.model.options['masked_training'], True)
        self.assertEqual(self.model.options['lr_dropout'], 'y')
        self.assertEqual(self.model.options['optimizer'], 'adabelief')

    def test_structural_parameters_protection(self):
        # Attempt to tamper with resolution on existing model (iter > 0)
        test_json = json.dumps({
            "resolution": 512,
            "batch_size": 32
        })
        self.model.options_json = test_json
        self.model.iter = 100 # existing model

        with patch('models.ModelBase.io.log_info'):
            self.model.load_train_step_config()

        # Resolution should remain untouched (128)
        self.assertEqual(self.model.options['resolution'], 128)
        # Batch size should be updated (32)
        self.assertEqual(self.model.options['batch_size'], 32)

    def test_ask_override_bypass(self):
        self.model.options_json = '{"batch_size": 8}'
        self.model.is_training = True
        
        with patch('models.ModelBase.io.log_info') as mock_log:
            result = self.model.ask_override()
            self.assertFalse(result)
            mock_log.assert_called_with("检测到 GUI 选项 JSON，自动跳过手动参数设置倒计时。")

    def test_save_interval_min_parsing(self):
        test_json = json.dumps({
            "save_interval_min": 10
        })
        self.model.options_json = test_json
        with patch('models.ModelBase.io.log_info'):
            self.model.load_train_step_config()

        self.assertEqual(self.model.options['save_interval_min'], 10)

    def test_persisted_misplaced_batch2_keys_warn_without_options_json(self):
        """R1-01: final self.options (from data.dat) must warn even without options-json."""
        self.model.options = {
            "batch_size": 4,
            "training": {"enabled": True},
            "sampling": {"mode": "pose_balanced"},
        }
        self.model.options_json = None
        with patch("models.ModelBase.io.log_info") as mock_log:
            self.model.load_train_step_config()

        warning_calls = [
            str(c.args[0]) for c in mock_log.call_args_list if c.args
        ]
        matched = [
            m for m in warning_calls
            if "Unsupported top-level Batch 2 config keys detected" in m
        ]
        self.assertEqual(len(matched), 1, msg=warning_calls)
        self.assertIn("training, sampling", matched[0])
        self.assertIn('Expected under "enhancements"', matched[0])
        # No auto-migration / deletion
        self.assertIn("training", self.model.options)
        self.assertIn("sampling", self.model.options)
        self.assertEqual(self.model.options["sampling"]["mode"], "pose_balanced")

    def test_options_json_misplaced_batch2_keys_warn_on_final_options(self):
        """R1-01: injected top-level Batch 2 keys also warn once on final options."""
        self.model.options_json = json.dumps({
            "batch_size": 8,
            "training": {"enabled": True, "metadata_sampling": True},
            "sampling": {"mode": "pose_balanced"},
        })
        with patch("models.ModelBase.io.log_info") as mock_log:
            self.model.load_train_step_config()

        warning_calls = [
            str(c.args[0]) for c in mock_log.call_args_list if c.args
        ]
        matched = [
            m for m in warning_calls
            if "Unsupported top-level Batch 2 config keys detected" in m
        ]
        self.assertEqual(len(matched), 1, msg=warning_calls)
        self.assertIn("training", matched[0])
        self.assertIn("sampling", matched[0])
        self.assertEqual(self.model.options["batch_size"], 8)

    def test_correct_nested_enhancements_no_misplaced_warning(self):
        self.model.options_json = json.dumps({
            "enhancements": {
                "training": {"enabled": True, "metadata_sampling": True},
                "sampling": {"mode": "pose_balanced"},
            }
        })
        with patch("models.ModelBase.io.log_info") as mock_log:
            self.model.load_train_step_config()

        warning_calls = [
            str(c.args[0]) for c in mock_log.call_args_list if c.args
        ]
        self.assertFalse(
            any("Unsupported top-level Batch 2 config keys detected" in m for m in warning_calls),
            msg=warning_calls,
        )
        self.assertIsInstance(self.model.options["enhancements"], dict)
        self.assertIsInstance(self.model.options["enhancements"]["sampling"], dict)

    def test_nested_enhancements_keep_mapping_type_via_load_train_step_config(self):
        payload = {
            "enhancements": {
                "schema_version": 1,
                "training": {"enabled": True, "metadata_sampling": True},
                "sampling": {
                    "src": {"mode": "quality_pose_balanced"},
                    "dst": {"mode": "pose_balanced"},
                },
            }
        }
        self.model.options_json = json.dumps(payload)
        with patch("models.ModelBase.io.log_info"):
            self.model.load_train_step_config()
        enh = self.model.options["enhancements"]
        self.assertIsInstance(enh, dict)
        self.assertIsInstance(enh["sampling"]["src"], dict)
        self.assertEqual(enh["sampling"]["src"]["mode"], "quality_pose_balanced")


if __name__ == '__main__':
    unittest.main()
