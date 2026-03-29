import os
import select
import sys
import termios
import time
import tty
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Optional


# Input event constants
INPUT_NONE = 0
INPUT_QUIT = 1
INPUT_LEFT = 2
INPUT_RIGHT = 3
INPUT_UP = 4
INPUT_DOWN = 5
INPUT_ENJOY = 8
INPUT_SPACE = 9


@dataclass
class Slider:
    name: str
    attr: str
    min_val: float
    max_val: float
    step: float
    fmt: str = ".1f"


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
        # Auto-size to terminal if size=0
        if size <= 0:
            try:
                ts = os.get_terminal_size()
                size = min(ts.columns, ts.lines - 3)
            except OSError:
                size = 25
        self.size = size
        self.speed = speed
        self.brightness = brightness
        self.ascii_mode = ascii_mode
        self.oneshot = oneshot
        self.frame = 0
        self.running = True
        self._old_term_settings: Optional[list] = None

    def clear_screen(self) -> str:
        return f"{self.ANSI_CLEAR}{self.ANSI_HOME}"

    @abstractmethod
    def render_frame(self) -> str:
        pass

    def reset(self) -> None:
        self.frame = 0
        self.running = True

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
            if event == INPUT_SPACE:
                return INPUT_SPACE
            if event != INPUT_NONE and on_event:
                on_event(event)

            output = self.clear_screen() + self.render_frame()
            sys.stdout.write(output)
            sys.stdout.flush()

            if on_frame:
                on_frame()

            if self.oneshot:
                break

            time.sleep(1.0 / self.speed)
            self.frame += 1
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

    def _check_input(self) -> int:
        if self._old_term_settings is None:
            return INPUT_NONE
        try:
            if not select.select([sys.stdin], [], [], 0)[0]:
                return INPUT_NONE
            ch = sys.stdin.read(1)
            if ch in ("q", "Q"):
                return INPUT_QUIT
            if ch in ("e", "E"):
                return INPUT_ENJOY
            if ch == " ":
                return INPUT_SPACE
            if ch == "\x1b":
                # Arrow keys send 3-byte sequences: ESC [ A/B/C/D
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    ch2 = sys.stdin.read(1)
                    if ch2 == "[" and select.select([sys.stdin], [], [], 0.1)[0]:
                        ch3 = sys.stdin.read(1)
                        if ch3 == "D":
                            return INPUT_LEFT
                        if ch3 == "C":
                            return INPUT_RIGHT
                        if ch3 == "A":
                            return INPUT_UP
                        if ch3 == "B":
                            return INPUT_DOWN
                        return INPUT_NONE
                # Bare ESC
                return INPUT_QUIT
        except (OSError, IOError):
            return INPUT_NONE
        return INPUT_NONE

    def _set_raw_mode(self) -> None:
        try:
            self._old_term_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        except (termios.error, AttributeError):
            self._old_term_settings = None

    def _restore_mode(self) -> None:
        if self._old_term_settings is not None:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_term_settings)
            self._old_term_settings = None

    def _enter_alt_screen(self) -> None:
        sys.stdout.write(self.ANSI_ALT_SCREEN_ON)
        sys.stdout.flush()

    def _exit_alt_screen(self) -> None:
        sys.stdout.write(self.ANSI_ALT_SCREEN_OFF)
        sys.stdout.flush()

    def _hide_cursor(self) -> None:
        sys.stdout.write(self.ANSI_HIDE_CURSOR)
        sys.stdout.flush()

    def _show_cursor(self) -> None:
        sys.stdout.write(self.ANSI_SHOW_CURSOR)
        sys.stdout.flush()

    def _cleanup(self) -> None:
        self._restore_mode()
        self._show_cursor()
        self._exit_alt_screen()
        sys.stdout.write(self.ANSI_RESET)
        sys.stdout.flush()
