import select
import sys
import termios
import time
import tty
from abc import ABC, abstractmethod
from typing import Optional


# Input event constants
INPUT_NONE = 0
INPUT_QUIT = 1
INPUT_LEFT = 2
INPUT_RIGHT = 3


class BaseVisualizer(ABC):
    ANSI_CLEAR = "\033[2J"
    ANSI_HOME = "\033[H"
    ANSI_RESET = "\033[0m"
    ANSI_HIDE_CURSOR = "\033[?25l"
    ANSI_SHOW_CURSOR = "\033[?25h"
    ANSI_ALT_SCREEN_ON = "\033[?1049h"
    ANSI_ALT_SCREEN_OFF = "\033[?1049l"

    def __init__(
        self,
        size: int = 25,
        speed: int = 5,
        brightness: int = 100,
        ascii_mode: bool = False,
        oneshot: bool = False,
    ):
        self.size = size
        self.speed = speed
        self.brightness = brightness
        self.ascii_mode = ascii_mode
        self.oneshot = oneshot
        self.frame = 0
        self.running = True
        self._old_term_settings: Optional[list] = None
        self._switch_direction: int = INPUT_NONE  # set when arrow key pressed

    def clear_screen(self) -> str:
        return f"{self.ANSI_CLEAR}{self.ANSI_HOME}"

    @abstractmethod
    def render_frame(self) -> str:
        pass

    def reset(self) -> None:
        """Reset frame counter for reuse when switching modes."""
        self.frame = 0
        self.running = True
        self._switch_direction = INPUT_NONE

    def run(self) -> None:
        """Standalone run with full terminal setup/teardown."""
        self._enter_alt_screen()
        self._hide_cursor()
        self._set_raw_mode()
        try:
            self.run_loop()
        except KeyboardInterrupt:
            pass
        finally:
            self._cleanup()

    def run_loop(self) -> int:
        """Run the render loop. Returns INPUT_QUIT, INPUT_LEFT, or INPUT_RIGHT."""
        self.running = True
        self._switch_direction = INPUT_NONE
        while self.running:
            event = self._check_input()
            if event == INPUT_QUIT:
                return INPUT_QUIT
            if event in (INPUT_LEFT, INPUT_RIGHT):
                self._switch_direction = event
                return event

            output = self.clear_screen() + self.render_frame()
            sys.stdout.write(output)
            sys.stdout.flush()

            if self.oneshot:
                break

            time.sleep(1.0 / self.speed)
            self.frame += 1
        return INPUT_QUIT

    def _check_input(self) -> int:
        if self._old_term_settings is None:
            return INPUT_NONE
        if select.select([sys.stdin], [], [], 0)[0]:
            ch = sys.stdin.read(1)
            if ch in ("q", "Q"):
                return INPUT_QUIT
            if ch == "\x1b":
                # Could be ESC or start of arrow key sequence
                if select.select([sys.stdin], [], [], 0.05)[0]:
                    ch2 = sys.stdin.read(1)
                    if ch2 == "[":
                        if select.select([sys.stdin], [], [], 0.05)[0]:
                            ch3 = sys.stdin.read(1)
                            if ch3 == "D":  # left arrow
                                return INPUT_LEFT
                            if ch3 == "C":  # right arrow
                                return INPUT_RIGHT
                # Bare ESC (no follow-up bytes)
                return INPUT_QUIT
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
