import os
import re
import sys
import traceback

from src.base import (
    BaseVisualizer, INPUT_QUIT, INPUT_LEFT, INPUT_RIGHT,
    INPUT_UP, INPUT_DOWN, INPUT_ENJOY, INPUT_SPACE,
)
from src.waves import WaveVisualizer
from src.galaxy import GalaxyVisualizer
from src.spiral import SpiralVisualizer


MODE_NAMES = ["waves", "galaxy", "spiral"]

# Onboarding hint fades after this many frames
HINT_FRAMES = 40

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


class App:
    def __init__(
        self,
        start_mode: str = "waves",
        size: int = 0,
        speed: int = 5,
        brightness: int = 100,
        ascii_mode: bool = False,
        oneshot: bool = False,
        wave_count: int = 3,
        foam: bool = True,
        arms: int = 2,
        twinkle: bool = True,
        arm_gap: int = 2,
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
        self.enjoy_mode = False
        self.total_frames = 0  # tracks frames across mode switches for hint fade

    @property
    def current(self) -> BaseVisualizer:
        return self.visualizers[self.index]

    def run(self) -> None:
        first = self.current
        first._enter_alt_screen()
        first._hide_cursor()
        first._set_raw_mode()
        self._term_settings = first._old_term_settings
        try:
            while True:
                vis = self.current
                vis._old_term_settings = self._term_settings

                result = vis.run_loop(
                    on_frame=self._draw_hud,
                    on_event=self._handle_event,
                )
                self.total_frames = max(self.total_frames, vis.frame)

                if result == INPUT_QUIT:
                    break
                elif result == INPUT_SPACE:
                    self.index = (self.index + 1) % len(self.visualizers)
                    self.current.reset()
        except KeyboardInterrupt:
            pass
        except Exception:
            with open("/tmp/freio_crash.log", "w") as f:
                traceback.print_exc(file=f)
        finally:
            first._old_term_settings = self._term_settings
            first._restore_mode()
            first._show_cursor()
            first._exit_alt_screen()
            sys.stdout.write(first.ANSI_RESET)
            sys.stdout.flush()

    def _handle_event(self, event: int) -> bool:
        vis = self.current
        if event == INPUT_LEFT:
            vis.adjust_slider(0, -1)
        elif event == INPUT_RIGHT:
            vis.adjust_slider(0, 1)
        elif event == INPUT_UP:
            vis.adjust_slider(1, 1)
        elif event == INPUT_DOWN:
            vis.adjust_slider(1, -1)
        elif event == INPUT_ENJOY:
            self.enjoy_mode = not self.enjoy_mode
        return True

    def _draw_hud(self) -> None:
        self.total_frames += 1

        if self.enjoy_mode:
            return

        try:
            cols = os.get_terminal_size().columns
            rows = os.get_terminal_size().lines
        except OSError:
            cols, rows = 80, 24

        vis = self.current
        ascii_mode = vis.ascii_mode
        bar_full = "=" if ascii_mode else "\u2588"
        bar_empty = "-" if ascii_mode else "\u2591"
        sep_char = "-" if ascii_mode else "\u2500"
        lr_arrow = "<>" if ascii_mode else "\u2190\u2192"
        ud_arrow = "^v" if ascii_mode else "\u2191\u2193"

        # --- Slider line ---
        slider_parts = []
        arrows = [lr_arrow, ud_arrow]
        for i, s in enumerate(vis.sliders):
            val = getattr(vis, s.attr)
            ratio = (val - s.min_val) / max(0.001, s.max_val - s.min_val)
            bar_len = 10
            filled = int(ratio * bar_len)
            bar = bar_full * filled + bar_empty * (bar_len - filled)
            val_str = str(int(val)) if s.fmt == "d" else f"{val:{s.fmt}}"
            axis = arrows[i] if i < len(arrows) else ""
            slider_parts.append(f"\033[96m{axis} {s.name}\033[0m [{bar}] {val_str}")

        hud_sliders = "   ".join(slider_parts)

        # --- Mode nav line ---
        name = MODE_NAMES[self.index].upper()
        dot = "o" if ascii_mode else "\u25CF"
        mode_str = f" {dot}  {name}  {dot} "

        # --- Separator line ---
        sep_line = sep_char * cols

        # --- Onboarding hint (fades after HINT_FRAMES) ---
        hint_str = ""
        if self.total_frames < HINT_FRAMES:
            opacity = max(0, HINT_FRAMES - self.total_frames) / HINT_FRAMES
            if opacity > 0.5:
                hint_color = "\033[90m"
            elif opacity > 0:
                hint_color = "\033[90;2m"
            else:
                hint_color = ""
            if hint_color:
                hint_str = f"{hint_color}space next   \u2190\u2192 {vis.sliders[0].name.lower() if vis.sliders else ''}   \u2191\u2193 {vis.sliders[1].name.lower() if len(vis.sliders) > 1 else ''}   e enjoy   q quit\033[0m"

        # Layout: 3 lines at bottom (separator, sliders, mode)
        # Optional 4th line for hint
        slider_plain_len = len(_ANSI_RE.sub("", hud_sliders))
        pad_s = max(0, (cols - slider_plain_len) // 2)
        pad_m = max(0, (cols - len(mode_str)) // 2)

        y_sep = rows - 3
        y_slider = rows - 2
        y_mode = rows - 1

        dim = "\033[90m"
        bright = "\033[97;1m"
        reset = "\033[0m"

        out = []
        # Separator
        out.append(f"\033[{y_sep};1H\033[2K{dim}{sep_line}{reset}")
        # Sliders
        out.append(f"\033[{y_slider};1H\033[2K\033[100m{' ' * cols}\033[{y_slider};{pad_s}H\033[100m{hud_sliders}{reset}")
        # Mode nav
        out.append(f"\033[{y_mode};1H\033[2K\033[100m{' ' * cols}\033[{y_mode};{pad_m}H\033[100m{bright}{mode_str}{reset}")

        # Hint overlay (centered, above separator)
        if hint_str:
            hint_plain_len = len(_ANSI_RE.sub("", hint_str))
            pad_h = max(0, (cols - hint_plain_len) // 2)
            y_hint = y_sep - 1
            out.append(f"\033[{y_hint};1H\033[2K\033[{y_hint};{pad_h}H{hint_str}")

        sys.stdout.write("".join(out))
        sys.stdout.flush()
