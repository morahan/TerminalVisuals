import os
import sys
import time

from src.base import BaseVisualizer, INPUT_QUIT, INPUT_LEFT, INPUT_RIGHT
from src.waves import WaveVisualizer
from src.galaxy import GalaxyVisualizer
from src.spiral import SpiralVisualizer


MODE_NAMES = ["waves", "galaxy", "spiral"]


class App:
    """Controls mode switching between visualizers via arrow keys."""

    def __init__(
        self,
        start_mode: str = "waves",
        size: int = 25,
        speed: int = 5,
        brightness: int = 100,
        ascii_mode: bool = False,
        oneshot: bool = False,
        # wave options
        wave_count: int = 3,
        foam: bool = True,
        # galaxy options
        arms: int = 2,
        twinkle: bool = True,
        arm_gap: int = 2,
        # spiral options
        trail: int = 4,
    ):
        common = dict(size=size, speed=speed, brightness=brightness,
                      ascii_mode=ascii_mode, oneshot=oneshot)

        self.visualizers: list[BaseVisualizer] = [
            WaveVisualizer(**common, wave_count=wave_count, foam=foam),
            GalaxyVisualizer(**common, arms=arms, twinkle=twinkle, arm_gap=arm_gap),
            SpiralVisualizer(**common, arm_gap=arm_gap, trail=trail),
        ]
        self.index = MODE_NAMES.index(start_mode) if start_mode in MODE_NAMES else 0

    @property
    def current(self) -> BaseVisualizer:
        return self.visualizers[self.index]

    def run(self) -> None:
        vis = self.current
        vis._enter_alt_screen()
        vis._hide_cursor()
        vis._set_raw_mode()
        try:
            while True:
                vis = self.current
                vis.reset()
                # Share terminal state across visualizers
                vis._old_term_settings = self.visualizers[0]._old_term_settings

                self._show_mode_label()
                result = vis.run_loop()

                if result == INPUT_QUIT:
                    break
                elif result == INPUT_LEFT:
                    self.index = (self.index - 1) % len(self.visualizers)
                elif result == INPUT_RIGHT:
                    self.index = (self.index + 1) % len(self.visualizers)
        except KeyboardInterrupt:
            pass
        finally:
            vis._restore_mode()
            vis._show_cursor()
            vis._exit_alt_screen()
            sys.stdout.write(vis.ANSI_RESET)
            sys.stdout.flush()

    def _show_mode_label(self) -> None:
        """Flash the mode name briefly on switch."""
        name = MODE_NAMES[self.index].upper()
        try:
            cols = os.get_terminal_size().columns
            rows = os.get_terminal_size().lines
        except OSError:
            cols, rows = 80, 24

        # Build indicator: < WAVES >  or  < GALAXY >  etc.
        left_arrow = "\u25C0" if not self.current.ascii_mode else "<"
        right_arrow = "\u25B6" if not self.current.ascii_mode else ">"
        label = f" {left_arrow}  {name}  {right_arrow} "
        pad_x = max(0, (cols - len(label)) // 2)
        pos_y = rows - 1

        sys.stdout.write(f"\033[{pos_y};1H\033[2K")  # move to bottom, clear line
        sys.stdout.write(f"\033[{pos_y};{pad_x}H")
        sys.stdout.write(f"\033[97;1m{label}\033[0m")
        sys.stdout.flush()
