import math
import os
import sys
import time
import select
import termios
import tty
from typing import List, Optional, Tuple

from .config import (
    SpiralConfig, COLOR_SCHEMES, RAINBOW_COLORS, RESET,
)
from .chars import get_charset, get_trail_chars


class SpiralVisualizer:
    def __init__(self, config: SpiralConfig):
        self.config = config
        self.charset = get_charset(config.ascii_only)
        self.trail_chars = get_trail_chars(config.ascii_only)
        self.theta = 0.0
        self.frame = 0
        self.points: List[Tuple[int, int, float]] = []  # (x, y, age)
        self._old_settings: Optional[list] = None

        # Spiral parameters
        self.a = 0.0  # starting radius
        self.b = 0.3 / max(1, config.ring_gap)  # growth rate per radian
        self.theta_step = 0.15
        self.max_radius = (config.size // 2) - 1
        self.total_steps = int(self.max_radius / self.b / self.theta_step) if self.b > 0 else 200

    def run(self) -> None:
        self._enter_alt_screen()
        self._hide_cursor()
        self._set_raw_mode()
        try:
            while True:
                self._reset()
                self._animate_spiral()
                self._hold_and_fade()
                if self.config.oneshot:
                    break
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            self._restore_mode()
            self._show_cursor()
            self._exit_alt_screen()

    def _reset(self) -> None:
        self.theta = 0.0
        self.frame = 0
        self.points = []

    def _animate_spiral(self) -> None:
        points_per_frame = max(1, 6 - self.config.speed)
        for step in range(self.total_steps):
            if self._check_quit():
                raise SystemExit
            for _ in range(points_per_frame):
                self.theta += self.theta_step
                if self.config.reverse:
                    angle = -self.theta
                else:
                    angle = self.theta
                r = self.a + self.b * self.theta
                if r > self.max_radius:
                    break
                x = int(round(r * math.cos(angle)))
                y = int(round(r * math.sin(angle) * 0.5))  # half for aspect ratio
                self.points.append((x, y, 0.0))

            self._age_points()
            self._render()
            self._sleep()
            self.frame += 1

    def _hold_and_fade(self) -> None:
        # Hold the complete spiral briefly
        for _ in range(15):
            if self._check_quit():
                raise SystemExit
            self._render()
            self._sleep()

        # Fade out by aging all points rapidly
        for _ in range(len(self.trail_chars) + self.config.trail + 5):
            if self._check_quit():
                raise SystemExit
            for i in range(len(self.points)):
                x, y, age = self.points[i]
                self.points[i] = (x, y, age + 0.5)
            self._render()
            self._sleep()

    def _age_points(self) -> None:
        trail_len = self.config.trail
        new_points = []
        for x, y, age in self.points:
            new_age = age + 0.08
            if new_age < trail_len + len(self.trail_chars):
                new_points.append((x, y, new_age))
        self.points = new_points

    def _render(self) -> None:
        size = self.config.size
        cx = size // 2
        cy = size // 2
        grid: List[List[str]] = [[" " for _ in range(size)] for _ in range(size)]

        # Sort points by age (oldest first, so newest overwrites)
        sorted_points = sorted(self.points, key=lambda p: -p[2])

        for x, y, age in sorted_points:
            gx = cx + x
            gy = cy + y
            if 0 <= gx < size and 0 <= gy < size:
                char, color = self._style_point(x, y, age)
                if char.strip():  # don't overwrite with spaces
                    grid[gy][gx] = f"{color}{char}{RESET}"

        # Add center dot
        center_char = self.charset["dot"]
        bright_color = self._get_colors(0)[1]
        pulse = 0.5 + 0.5 * math.sin(self.frame * 0.2)
        if pulse > 0.3:
            grid[cy][cx] = f"{bright_color}\033[1m{center_char}{RESET}"

        # Build output
        term_cols = os.get_terminal_size().columns
        term_rows = os.get_terminal_size().lines
        pad_x = max(0, (term_cols - size) // 2)
        pad_y = max(0, (term_rows - size) // 2)

        lines = ["\033[H"]  # cursor home
        # Top padding
        for _ in range(pad_y):
            lines.append("\033[2K\n")
        for row in grid:
            lines.append("\033[2K" + " " * pad_x + "".join(row) + "\n")
        # Clear remaining lines
        remaining = term_rows - pad_y - size
        for _ in range(max(0, remaining)):
            lines.append("\033[2K\n")

        sys.stdout.write("".join(lines))
        sys.stdout.flush()

    def _style_point(self, x: int, y: int, age: float) -> Tuple[str, str]:
        trail = self.config.trail
        dist = math.sqrt(x * x + y * y)
        ring_idx = int(dist / max(1, self.config.ring_gap))

        primary, bright, dim = self._get_colors(ring_idx)

        brightness_factor = self.config.brightness / 100.0

        if age < 0.5:
            # Newest point — bright glow
            char = self.charset["bright"]
            color = f"{bright}\033[1m" if brightness_factor > 0.5 else bright
        elif age < trail * 0.3:
            char = self.trail_chars[0]
            color = bright
        elif age < trail * 0.6:
            char = self.trail_chars[min(1, len(self.trail_chars) - 1)]
            color = primary
        elif age < trail:
            idx = min(2, len(self.trail_chars) - 1)
            char = self.trail_chars[idx]
            color = primary
        else:
            fade_idx = min(int(age - trail), len(self.trail_chars) - 1)
            char = self.trail_chars[fade_idx]
            color = dim

        if brightness_factor < 0.5:
            color = f"\033[2m{color}"

        return char, color

    def _get_colors(self, ring_idx: int) -> Tuple[str, str, str]:
        if self.config.colors == "rainbow":
            idx = ring_idx % len(RAINBOW_COLORS)
            return RAINBOW_COLORS[idx]
        return COLOR_SCHEMES[self.config.colors]

    def _sleep(self) -> None:
        base = 0.02 + (self.config.speed * 0.008)
        time.sleep(base)

    def _check_quit(self) -> bool:
        if self._old_settings is None:
            return False
        if select.select([sys.stdin], [], [], 0)[0]:
            ch = sys.stdin.read(1)
            if ch in ("q", "Q", "\x1b"):  # q or Escape
                return True
        return False

    def _set_raw_mode(self) -> None:
        try:
            self._old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        except (termios.error, AttributeError):
            self._old_settings = None

    def _restore_mode(self) -> None:
        if self._old_settings is not None:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_settings)
            self._old_settings = None

    def _enter_alt_screen(self) -> None:
        sys.stdout.write("\033[?1049h")
        sys.stdout.write("\033[2J")
        sys.stdout.flush()

    def _exit_alt_screen(self) -> None:
        sys.stdout.write("\033[?1049l")
        sys.stdout.flush()

    def _hide_cursor(self) -> None:
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

    def _show_cursor(self) -> None:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
