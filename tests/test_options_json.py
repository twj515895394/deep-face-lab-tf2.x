import unittest
import json
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Ensure repository root is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock missing heavy packages if running in minimal environment
for mod_name in ['scipy', 'scipy.spatial', 'cv2', 'tensorflow', 'numexpr', 'h5py']:
    if mod_name not in sys.modules:
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

if __name__ == '__main__':
    unittest.main()
