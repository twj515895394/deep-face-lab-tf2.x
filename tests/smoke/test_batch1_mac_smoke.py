import json
import tempfile
import unittest
from pathlib import Path

from tools.smoke import batch1_mac_smoke


class Batch1MacSmokeTest(unittest.TestCase):
    def test_collect_environment_records_windows_gpu_gap(self):
        environment = batch1_mac_smoke.collect_environment()

        self.assertIn("git", environment)
        self.assertIn("python", environment)
        self.assertIn("platform", environment)
        self.assertIn("windows_gpu_validation_required", environment)
        self.assertGreater(
            len(environment["windows_gpu_validation_required"]),
            0,
        )

    def test_lightweight_checks_pass_on_repository_structure(self):
        summary = batch1_mac_smoke.run_lightweight_checks()

        self.assertEqual("pass", summary["status"])
        self.assertTrue(summary["checks"]["git_metadata_available"])
        self.assertTrue(summary["checks"]["gpu_training_skipped_by_design"])
        self.assertTrue(
            all(summary["checks"]["required_files"].values()),
            summary["checks"]["required_files"],
        )
        self.assertGreater(summary["checks"]["syntax_scan"]["files_scanned"], 0)
        self.assertEqual([], summary["checks"]["syntax_scan"]["errors"])

    def test_write_smoke_outputs_creates_json_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            environment = {"python": {"version": "test"}}
            summary = {"status": "pass"}

            batch1_mac_smoke.write_smoke_outputs(
                output_dir,
                environment,
                summary,
            )

            self.assertEqual(
                environment,
                json.loads((output_dir / "environment.json").read_text()),
            )
            self.assertEqual(
                summary,
                json.loads((output_dir / "smoke-summary.json").read_text()),
            )


if __name__ == "__main__":
    unittest.main()
