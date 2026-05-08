import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.app import App, MODE_NAMES, SCREEN_CONSENT, SCREEN_NORMAL, SCREEN_OPT_OUT_LOCKED, SCREEN_SETTINGS
from src.base import INPUT_LOCK, INPUT_NO, INPUT_RIGHT, INPUT_SPACE, INPUT_YES
from src.settings import AppSettings, load_settings, save_settings


class AppSettingsBehaviorTests(unittest.TestCase):
    def test_startup_uses_locked_mode_and_sliders_without_cli_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            save_settings(
                AppSettings(
                    crash_reporting_opt_in=True,
                    locked_mode="galaxy",
                    locked_sliders={"depth": 0.35, "drift": 2.0},
                ),
                path,
            )

            with mock.patch.dict(os.environ, {}, clear=True):
                app = App(size=4, settings_path=path)

            self.assertEqual(MODE_NAMES[app.index], "galaxy")
            self.assertEqual(app.current.depth, 0.35)
            self.assertEqual(app.current.drift, 2.0)
            self.assertEqual(app.screen, SCREEN_NORMAL)

    def test_cli_mode_overrides_locked_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            save_settings(
                AppSettings(
                    crash_reporting_opt_in=True,
                    locked_mode="galaxy",
                    locked_sliders={"depth": 0.35},
                ),
                path,
            )

            with mock.patch.dict(os.environ, {}, clear=True):
                app = App(start_mode="waves", size=4, settings_path=path)

            self.assertEqual(MODE_NAMES[app.index], "waves")
            self.assertEqual(app.current.amplitude, 3.0)

    def test_lock_event_saves_current_mode_and_slider_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            save_settings(AppSettings(crash_reporting_opt_in=True), path)
            with mock.patch.dict(os.environ, {}, clear=True):
                app = App(start_mode="waves", size=4, settings_path=path)
            app.current.amplitude = 5.0
            app.current.frequency = 0.45

            self.assertTrue(app._handle_event(INPUT_LOCK))

            settings = load_settings(path)
            self.assertEqual(settings.locked_mode, "waves")
            self.assertEqual(settings.locked_sliders, {"amplitude": 5.0, "frequency": 0.45})

    def test_settings_overlay_blocks_slider_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            save_settings(AppSettings(crash_reporting_opt_in=True), path)
            with mock.patch.dict(os.environ, {}, clear=True):
                app = App(start_mode="waves", size=4, settings_path=path)
            app.screen = SCREEN_SETTINGS
            before = app.current.amplitude

            self.assertTrue(app._handle_event(INPUT_RIGHT))

            self.assertEqual(app.current.amplitude, before)

    def test_consent_yes_saves_opt_in_and_enters_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            with mock.patch.dict(os.environ, {}, clear=True):
                app = App(start_mode="waves", size=4, settings_path=path)

            self.assertEqual(app.screen, SCREEN_CONSENT)
            self.assertTrue(app._handle_event(INPUT_YES))

            self.assertEqual(app.screen, SCREEN_NORMAL)
            self.assertTrue(load_settings(path).crash_reporting_enabled)

    def test_consent_no_saves_opt_out_and_locks_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            with mock.patch.dict(os.environ, {}, clear=True):
                app = App(start_mode="waves", size=4, settings_path=path)

            self.assertEqual(app.screen, SCREEN_CONSENT)
            self.assertTrue(app._handle_event(INPUT_NO))

            self.assertEqual(app.screen, SCREEN_OPT_OUT_LOCKED)
            self.assertFalse(load_settings(path).crash_reporting_enabled)

    def test_opt_out_lock_ignores_space_navigation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            save_settings(AppSettings(crash_reporting_opt_in=False), path)
            with mock.patch.dict(os.environ, {}, clear=True):
                app = App(start_mode="waves", size=4, settings_path=path)
            app.screen = SCREEN_OPT_OUT_LOCKED

            self.assertTrue(app._handle_event(INPUT_SPACE))

            self.assertEqual(MODE_NAMES[app.index], "waves")


if __name__ == "__main__":
    unittest.main()
