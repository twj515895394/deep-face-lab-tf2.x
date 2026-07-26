import unittest
import warnings

from core.enhancements import (
    EnhancementConfig,
    SUPPORTED_SCHEMA_VERSION,
    normalize_enhancement_config,
)


class Batch1EnhancementConfigDefaultsTest(unittest.TestCase):
    def test_none_input_disables_all_enhancements(self):
        cfg = normalize_enhancement_config(None)

        self.assertFalse(cfg.training_enabled)
        self.assertFalse(cfg.merge_enabled)
        self.assertFalse(cfg.is_enabled("training.loss_hooks"))
        self.assertFalse(cfg.is_enabled("merge.shape_aware_warp"))
        self.assertTrue(cfg.fallback_on_optional_error)
        self.assertFalse(cfg.strict_validation)

    def test_empty_dict_disables_all_enhancements(self):
        cfg = normalize_enhancement_config({})

        self.assertEqual(SUPPORTED_SCHEMA_VERSION, cfg.schema_version)
        self.assertFalse(cfg.training_enabled)
        self.assertFalse(cfg.merge_enabled)

    def test_single_training_flag_does_not_enable_other_flags(self):
        cfg = EnhancementConfig.from_mapping(
            {
                "schema_version": 1,
                "training": {"enabled": True, "loss_hooks": True},
            }
        )

        self.assertTrue(cfg.training_enabled)
        self.assertTrue(cfg.is_enabled("training.loss_hooks"))
        self.assertFalse(cfg.is_enabled("training.identity_geometry"))
        self.assertFalse(cfg.merge_enabled)
        self.assertFalse(cfg.is_enabled("merge.shape_aware_mask"))

    def test_subflag_is_ignored_when_section_disabled(self):
        cfg = EnhancementConfig.from_mapping(
            {"training": {"enabled": False, "loss_hooks": True}}
        )

        self.assertFalse(cfg.training_enabled)
        self.assertFalse(cfg.is_enabled("training.loss_hooks"))

    def test_unknown_section_fields_do_not_enable_behavior(self):
        cfg = EnhancementConfig.from_mapping(
            {
                "training": {"enabled": True, "unknown_future_flag": True},
                "merge": {"enabled": True, "unknown_merge_flag": "true"},
            }
        )

        self.assertFalse(cfg.is_enabled("training.unknown_future_flag"))
        self.assertFalse(cfg.is_enabled("merge.unknown_merge_flag"))
        self.assertNotIn("unknown_future_flag", cfg.to_dict()["training"])
        self.assertNotIn("unknown_merge_flag", cfg.to_dict()["merge"])

    def test_bool_strings_are_normalized_and_bad_values_keep_default(self):
        cfg = EnhancementConfig.from_mapping(
            {
                "training": {
                    "enabled": "true",
                    "loss_hooks": "1",
                    "identity_geometry": "not-a-bool",
                },
                "runtime": {"fallback_on_optional_error": "false"},
            }
        )

        self.assertTrue(cfg.training_enabled)
        self.assertTrue(cfg.is_enabled("training.loss_hooks"))
        self.assertFalse(cfg.is_enabled("training.identity_geometry"))
        self.assertFalse(cfg.fallback_on_optional_error)

    def test_unsupported_schema_warns_and_disables_enhancements(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            cfg = EnhancementConfig.from_mapping(
                {
                    "schema_version": 99,
                    "training": {"enabled": True, "loss_hooks": True},
                    "merge": {"enabled": True},
                }
            )

        self.assertTrue(caught)
        self.assertFalse(cfg.training_enabled)
        self.assertFalse(cfg.merge_enabled)
        self.assertFalse(cfg.is_enabled("training.loss_hooks"))

    def test_to_dict_roundtrip_is_stable_and_copy_safe(self):
        raw = {
            "schema_version": 1,
            "training": {"enabled": True, "loss_hooks": True},
            "runtime": {"strict_validation": False},
            "custom_metadata": {"source": "test"},
        }
        cfg = EnhancementConfig.from_mapping(raw)
        exported = cfg.to_dict()
        exported["training"]["loss_hooks"] = False

        self.assertTrue(cfg.is_enabled("training.loss_hooks"))
        self.assertEqual(
            cfg.to_dict(),
            EnhancementConfig.from_mapping(cfg.to_dict()).to_dict(),
        )

    def test_legacy_options_without_enhancements_are_safe(self):
        legacy_options = {
            "resolution": 128,
            "face_type": "f",
            "eyes_mouth_prio": True,
        }

        cfg = normalize_enhancement_config(legacy_options.get("enhancements"))
        self.assertFalse(cfg.training_enabled)
        self.assertFalse(cfg.merge_enabled)


if __name__ == "__main__":
    unittest.main()
