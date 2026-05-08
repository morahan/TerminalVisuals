import io
import signal
import unittest
from unittest import mock

from src import app
from src.base import BaseVisualizer


class TerminalLifecycleTests(unittest.TestCase):
    def test_terminal_session_restores_cursor_alt_screen_mode_and_signals(self):
        stdout = io.StringIO()
        stdin = mock.Mock()
        stdin.fileno.return_value = 0
        stopped = []

        with (
            mock.patch.object(app.termios, "tcgetattr", return_value=["settings"]),
            mock.patch.object(app.tty, "setcbreak"),
            mock.patch.object(app.termios, "tcsetattr", side_effect=app.termios.error),
            mock.patch.object(app.signal, "getsignal", return_value=signal.SIG_DFL),
            mock.patch.object(app.signal, "signal") as signal_mock,
        ):
            session = app.TerminalSession(lambda: stopped.append(True), stdin=stdin, stdout=stdout)
            session.enter()
            session._handle_signal(signal.SIGTERM, None)
            session.restore()

        self.assertEqual(stopped, [True])
        self.assertEqual(session.received_signal, signal.SIGTERM)
        output = stdout.getvalue()
        self.assertIn(BaseVisualizer.ANSI_ALT_SCREEN_ON, output)
        self.assertIn(BaseVisualizer.ANSI_HIDE_CURSOR, output)
        self.assertIn(BaseVisualizer.ANSI_RESET, output)
        self.assertIn(BaseVisualizer.ANSI_SHOW_CURSOR, output)
        self.assertIn(BaseVisualizer.ANSI_ALT_SCREEN_OFF, output)
        self.assertGreaterEqual(signal_mock.call_count, 4)

    def test_terminal_session_tolerates_output_failures(self):
        stdout = mock.Mock()
        stdout.write.side_effect = OSError("closed")
        stdin = mock.Mock()
        stdin.fileno.return_value = 0

        with (
            mock.patch.object(app.termios, "tcgetattr", return_value=["settings"]),
            mock.patch.object(app.tty, "setcbreak"),
            mock.patch.object(app.termios, "tcsetattr"),
            mock.patch.object(app.signal, "getsignal", return_value=signal.SIG_DFL),
            mock.patch.object(app.signal, "signal"),
        ):
            session = app.TerminalSession(lambda: None, stdin=stdin, stdout=stdout)
            session.enter()
            session.restore()


if __name__ == "__main__":
    unittest.main()
