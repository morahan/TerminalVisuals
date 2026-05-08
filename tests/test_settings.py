import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.settings import (
    AppSettings,
    crash_reporting_state_requires_consent,
    load_settings,
    save_crash_reporting_opt_in,
    save_locked_animation,
    save_settings,
)


class SettingsTests(unittest.TestCase):
    def test_save_and_load_signed_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"

            saved = save_settings(
                AppSettings(
                    crash_reporting_opt_in=True,
                    locked_mode="galaxy",
                    locked_sliders={"depth": 0.3, "drift": 1.25},
                ),
                path,
            )
            loaded = load_settings(path)

            self.assertTrue(saved.checksum)
            self.assertFalse(loaded.corrupt)
            self.assertTrue(loaded.crash_reporting_enabled)
            self.assertEqual(loaded.locked_mode, "galaxy")
            self.assertEqual(loaded.locked_sliders, {"depth": 0.3, "drift": 1.25})

    def test_bad_checksum_falls_back_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            save_crash_reporting_opt_in(True, path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["crash_reporting_opt_in"] = False
            path.write_text(json.dumps(payload), encoding="utf-8")

            loaded = load_settings(path)

            self.assertTrue(loaded.corrupt)
            self.assertFalse(loaded.crash_reporting_enabled)
            self.assertIsNone(loaded.crash_reporting_opt_in)

    def test_migrates_legacy_consent_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "settings.json"
            legacy_path = Path(tmp) / "crash-reporting-consent.json"
            legacy_path.write_text(
                json.dumps(
                    {
                        "accepted": True,
                        "accepted_at": "2026-01-01T00:00:00+00:00",
                        "policy_version": 1,
                        "company": "Freio Labs, LLC",
                    }
                ),
                encoding="utf-8",
            )

            loaded = load_settings(settings_path, legacy_path=legacy_path)

            self.assertTrue(loaded.crash_reporting_enabled)
            self.assertTrue(settings_path.exists())
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertFalse(crash_reporting_state_requires_consent(loaded))

    def test_previous_opt_out_requires_consent_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            settings = save_crash_reporting_opt_in(False, path)

            self.assertFalse(settings.crash_reporting_enabled)
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertTrue(crash_reporting_state_requires_consent(load_settings(path)))

    def test_locked_animation_persists_without_consent_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            save_crash_reporting_opt_in(True, path)
            save_locked_animation("spiral", {"trail": 8, "growth": 0.4}, path)

            loaded = load_settings(path)

            self.assertTrue(loaded.crash_reporting_enabled)
            self.assertEqual(loaded.locked_mode, "spiral")
            self.assertEqual(loaded.locked_sliders, {"trail": 8, "growth": 0.4})


if __name__ == "__main__":
    unittest.main()
