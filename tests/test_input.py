import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src import base
from src.app import App, SCREEN_NORMAL
from src.base import (
    BaseVisualizer,
    INPUT_DOWN,
    INPUT_ESCAPE,
    INPUT_LEFT,
    INPUT_LOCK,
    INPUT_NONE,
    INPUT_NO,
    INPUT_RIGHT,
    INPUT_SETTINGS,
    INPUT_UP,
    INPUT_UNLOCK,
    INPUT_YES,
)


class InputProbe(BaseVisualizer):
    def render_frame(self) -> str:
        return ""


class FakeStdin:
    def __init__(self, data: str):
        self.data = data
        self.pos = 0

    def read(self, size: int = 1) -> str:
        if self.pos >= len(self.data):
            return ""
        chunk = self.data[self.pos:self.pos + size]
        self.pos += len(chunk)
        return chunk

    def has_data(self) -> bool:
        return self.pos < len(self.data)


def fake_select(reads, writes, errors, timeout=0):
    ready = [stream for stream in reads if getattr(stream, "has_data")()]
    return ready, writes, errors


class InputTests(unittest.TestCase):
    def _read_event(self, data: str) -> int:
        stdin = FakeStdin(data)
        vis = InputProbe(size=4)
        vis._old_term_settings = []
        with (
            mock.patch.object(base.sys, "stdin", stdin),
            mock.patch.object(base.select, "select", fake_select),
        ):
            return vis._check_input()

    def test_arrow_keys_decode_standard_csi_sequences(self):
        cases = {
            "\x1b[A": INPUT_UP,
            "\x1b[B": INPUT_DOWN,
            "\x1b[C": INPUT_RIGHT,
            "\x1b[D": INPUT_LEFT,
        }

        for data, expected in cases.items():
            with self.subTest(data=repr(data)):
                self.assertEqual(self._read_event(data), expected)

    def test_arrow_keys_decode_application_cursor_sequences(self):
        cases = {
            "\x1bOA": INPUT_UP,
            "\x1bOB": INPUT_DOWN,
            "\x1bOC": INPUT_RIGHT,
            "\x1bOD": INPUT_LEFT,
        }

        for data, expected in cases.items():
            with self.subTest(data=repr(data)):
                self.assertEqual(self._read_event(data), expected)

    def test_arrow_keys_decode_modified_csi_sequences(self):
        self.assertEqual(self._read_event("\x1b[1;5C"), INPUT_RIGHT)
        self.assertEqual(self._read_event("\x1b[1;2D"), INPUT_LEFT)

    def test_bare_escape_is_distinct_from_partial_unknown_sequences(self):
        self.assertEqual(self._read_event("\x1b"), INPUT_ESCAPE)
        self.assertEqual(self._read_event("\x1b["), INPUT_NONE)

    def test_settings_consent_and_lock_keys_decode(self):
        cases = {
            "s": INPUT_SETTINGS,
            "S": INPUT_SETTINGS,
            "l": INPUT_LOCK,
            "L": INPUT_LOCK,
            "y": INPUT_YES,
            "Y": INPUT_YES,
            "n": INPUT_NO,
            "N": INPUT_NO,
            "u": INPUT_UNLOCK,
            "U": INPUT_UNLOCK,
        }

        for data, expected in cases.items():
            with self.subTest(data=data):
                self.assertEqual(self._read_event(data), expected)

    def test_escape_only_leaves_fullscreen(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = App(size=4, settings_path=Path(tmp) / "settings.json")
        app.screen = SCREEN_NORMAL

        app.current.running = True
        app._handle_event(INPUT_ESCAPE)
        self.assertTrue(app.current.running)
        self.assertFalse(app.fullscreen)

        app._set_fullscreen(True)
        app._handle_event(INPUT_ESCAPE)
        self.assertTrue(app.current.running)
        self.assertFalse(app.fullscreen)


if __name__ == "__main__":
    unittest.main()
