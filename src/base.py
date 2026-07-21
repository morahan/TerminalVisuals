import os
import select
import sys
import termios
import time
import tty
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Optional


# Terminal characters are ~2x taller than wide
CHAR_ASPECT = 0.5
HUD_ROWS = 3
TARGET_FPS = 30
MAX_RENDER_CELLS = 12000

# Input event constants
INPUT_NONE = 0
INPUT_QUIT = 1
INPUT_LEFT = 2
INPUT_RIGHT = 3
INPUT_UP = 4
INPUT_DOWN = 5
INPUT_ENJOY = 8
INPUT_SPACE = 9
INPUT_FULLSCREEN = 10
INPUT_ESCAPE = 11
INPUT_REVERSE = 12
INPUT_SETTINGS = 13
INPUT_LOCK = 14
INPUT_YES = 15
INPUT_NO = 16
INPUT_UNLOCK = 17
INPUT_COLOR = 18


@dataclass
class Slider:
    name: str
    attr: str
    min_val: float
    max_val: float
    step: float
    fmt: str = ".1f"
    display: Optional[Callable[[float], str]] = None

    def format_value(self, value: float) -> str:
        if self.display is not None:
            return self.display(value)
        if self.fmt == "d":
            return str(int(value))
        return f"{value:{self.fmt}}"


class BaseVisualizer(ABC):
    ANSI_CLEAR = "\033[2J"
    ANSI_HOME = "\033[H"
    ANSI_RESET = "\033[0m"
    ANSI_HIDE_CURSOR = "\033[?25l"
    ANSI_SHOW_CURSOR = "\033[?25h"
    ANSI_ALT_SCREEN_ON = "\033[?1049h"
    ANSI_ALT_SCREEN_OFF = "\033[?1049l"

    sliders: list[Slider] = []

    def __init__(
        self,
        size: int = 0,
        speed: int = 5,
        brightness: int = 100,
        ascii_mode: bool = False,
        oneshot: bool = False,
    ):
        self.auto_size = size <= 0
        self.hud_rows = HUD_ROWS
        if self.auto_size:
            self.width, self.height = self._terminal_fit_dims()
        else:
            self.width = size
            self.height = size
        self.speed = speed
        self.brightness = brightness
        self.ascii_mode = ascii_mode
        self.oneshot = oneshot
        self.frame = 0.0
        self.running = True
        self.reversed = False
        self._old_term_settings: Optional[list] = None
        self._input_buffer = ""
        self._last_term_size = self._get_terminal_size()
        self._needs_full_clear = True

    def _get_terminal_size(self) -> tuple[int, int]:
        try:
            ts = os.get_terminal_size()
            return max(1, ts.columns), max(1, ts.lines)
        except OSError:
            return 80, 24

    def _terminal_fit_dims(self) -> tuple[int, int]:
        cols, lines = self._get_terminal_size()
        return self._fit_auto_dims(cols, lines)

    def _fit_auto_dims(self, cols: int, lines: int) -> tuple[int, int]:
        cols = max(1, cols)
        height = max(1, lines - self.hud_rows)
        if cols * height <= MAX_RENDER_CELLS:
            return cols, height
        return cols, max(1, MAX_RENDER_CELLS // cols)

    def _update_size(self) -> None:
        """Re-fit size to current terminal dimensions. Called each frame when auto_size is on."""
        term_size = self._get_terminal_size()
        if term_size != self._last_term_size:
            self._last_term_size = term_size
            self._needs_full_clear = True
        if not self.auto_size:
            return
        new_w, new_h = self._fit_auto_dims(*term_size)
        if new_w != self.width or new_h != self.height:
            self.width = new_w
            self.height = new_h
            self._needs_full_clear = True
            self._on_resize()

    def _on_resize(self) -> None:
        """Override in subclasses to react to size changes."""
        pass

    def set_hud_rows(self, rows: int) -> None:
        rows = max(0, rows)
        if rows == self.hud_rows:
            return
        self.hud_rows = rows
        self._needs_full_clear = True
        if not self.auto_size:
            return
        new_w, new_h = self._terminal_fit_dims()
        if new_w != self.width or new_h != self.height:
            self.width = new_w
            self.height = new_h
            self._on_resize()

    def clear_screen(self) -> str:
        if self._needs_full_clear:
            self._needs_full_clear = False
            return self.ANSI_CLEAR + self.ANSI_HOME
        return self.ANSI_HOME

    @abstractmethod
    def render_frame(self) -> str:
        pass

    def reset(self) -> None:
        self.frame = 0.0
        self.running = True

    def reverse(self) -> None:
        self.reversed = not self.reversed

    def run(self) -> None:
        self._enter_alt_screen()
        self._hide_cursor()
        self._set_raw_mode()
        try:
            self.run_loop()
        except KeyboardInterrupt:
            pass
        finally:
            self._cleanup()

    def run_loop(
        self,
        on_frame: Optional[Callable] = None,
        on_event: Optional[Callable[[int], bool]] = None,
    ) -> int:
        """Run render loop.

        on_frame: called after each frame render (for HUD overlay).
        on_event: called with event code for non-quit/non-nav events.
                  Return True if event was handled (stay in loop).
        Returns INPUT_QUIT or INPUT_SPACE.
        """
        self.running = True
        while self.running:
            event = self._check_input()
            if event == INPUT_QUIT:
                return INPUT_QUIT
            handled = False
            if event != INPUT_NONE and on_event:
                handled = on_event(event)
            if event == INPUT_SPACE and not handled:
                return INPUT_SPACE

            self._update_size()
            output = self.clear_screen() + self.render_frame()

            if on_frame:
                output += on_frame()

            try:
                sys.stdout.buffer.write(output.encode())
                sys.stdout.buffer.flush()
            except (BrokenPipeError, OSError):
                self.running = False
                return INPUT_QUIT

            if self.oneshot:
                break

            time.sleep(1.0 / TARGET_FPS)
            self.frame += self.speed / TARGET_FPS
        return INPUT_QUIT

    def adjust_slider(self, slider_idx: int, direction: int) -> None:
        if slider_idx < 0 or slider_idx >= len(self.sliders):
            return
        s = self.sliders[slider_idx]
        current = getattr(self, s.attr)
        if direction > 0:
            new_val = min(s.max_val, current + s.step)
        else:
            new_val = max(s.min_val, current - s.step)
        if s.step == int(s.step) and s.min_val == int(s.min_val):
            new_val = int(new_val)
        setattr(self, s.attr, new_val)

    def _read_input_chunk(self, timeout: float) -> str:
        """Read terminal bytes directly, avoiding TextIO's hidden read-ahead buffer."""
        if not select.select([sys.stdin], [], [], timeout)[0]:
            return ""
        try:
            return os.read(sys.stdin.fileno(), 32).decode(errors="ignore")
        except (AttributeError, OSError, ValueError):
            # Keep the input seam testable with stream-like stand-ins.
            return sys.stdin.read(1)

    @staticmethod
    def _key_event(ch: str) -> int:
        key_events = {
            "q": INPUT_QUIT,
            "Q": INPUT_QUIT,
            "e": INPUT_ENJOY,
            "E": INPUT_ENJOY,
            "f": INPUT_FULLSCREEN,
            "F": INPUT_FULLSCREEN,
            "r": INPUT_REVERSE,
            "R": INPUT_REVERSE,
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
            "c": INPUT_COLOR,
            "C": INPUT_COLOR,
            " ": INPUT_SPACE,
        }
        return key_events.get(ch, INPUT_NONE)

    def _arrow_event(self) -> tuple[int, int]:
        """Return the decoded event plus the number of buffered bytes consumed."""
        if not self._input_buffer:
            return INPUT_ESCAPE, 0
        prefix = self._input_buffer[0]
        if prefix == "O":
            if len(self._input_buffer) < 2:
                return INPUT_NONE, 0
            final = self._input_buffer[1]
            consumed = 2
        elif prefix == "[":
            final_idx = next(
                (idx for idx, char in enumerate(self._input_buffer[1:], start=1) if char.isalpha() or char == "~"),
                None,
            )
            if final_idx is None:
                return INPUT_NONE, 0
            final = self._input_buffer[final_idx]
            consumed = final_idx + 1
        else:
            return INPUT_ESCAPE, 0
        return {
            "A": INPUT_UP,
            "B": INPUT_DOWN,
            "C": INPUT_RIGHT,
            "D": INPUT_LEFT,
        }.get(final, INPUT_NONE), consumed

    def _check_input(self) -> int:
        if self._old_term_settings is None:
            return INPUT_NONE
        try:
            if not self._input_buffer:
                self._input_buffer = self._read_input_chunk(0)
            if not self._input_buffer:
                return INPUT_NONE

            ch = self._input_buffer[0]
            self._input_buffer = self._input_buffer[1:]
            if ch != "\x1b":
                return self._key_event(ch)

            # Arrow keys are escape sequences. Read from the file descriptor rather
            # than TextIO so all bytes from the first physical keypress stay visible.
            if not self._input_buffer:
                self._input_buffer = self._read_input_chunk(0.03)
            event, consumed = self._arrow_event()
            for _ in range(8):
                if event != INPUT_NONE or consumed or self._input_buffer[:1] not in ("[", "O"):
                    break
                next_chunk = self._read_input_chunk(0.03)
                if not next_chunk:
                    break
                self._input_buffer += next_chunk
                event, consumed = self._arrow_event()
            if consumed:
                self._input_buffer = self._input_buffer[consumed:]
            elif self._input_buffer[:1] in ("[", "O"):
                # Keep an incomplete sequence intact until its final byte arrives.
                self._input_buffer = "\x1b" + self._input_buffer
            return event
        except (OSError, IOError, ValueError):
            return INPUT_NONE

    def _set_raw_mode(self) -> None:
        try:
            self._old_term_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        except (termios.error, AttributeError):
            self._old_term_settings = None

    def _restore_mode(self) -> None:
        if self._old_term_settings is not None:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_term_settings)
            except (termios.error, AttributeError, OSError):
                pass
            finally:
                self._old_term_settings = None

    def _enter_alt_screen(self) -> None:
        try:
            sys.stdout.write(self.ANSI_ALT_SCREEN_ON)
            sys.stdout.flush()
        except (BrokenPipeError, OSError):
            pass

    def _exit_alt_screen(self) -> None:
        try:
            sys.stdout.write(self.ANSI_ALT_SCREEN_OFF)
            sys.stdout.flush()
        except (BrokenPipeError, OSError):
            pass

    def _hide_cursor(self) -> None:
        try:
            sys.stdout.write(self.ANSI_HIDE_CURSOR)
            sys.stdout.flush()
        except (BrokenPipeError, OSError):
            pass

    def _show_cursor(self) -> None:
        try:
            sys.stdout.write(self.ANSI_SHOW_CURSOR)
            sys.stdout.flush()
        except (BrokenPipeError, OSError):
            pass

    def _cleanup(self) -> None:
        try:
            sys.stdout.write(self.ANSI_RESET)
            sys.stdout.flush()
        except (BrokenPipeError, OSError):
            pass
        self._show_cursor()
        self._exit_alt_screen()
        self._restore_mode()
