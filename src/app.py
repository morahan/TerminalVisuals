import os
import re
import signal
import sys
import termios
import tty
from types import FrameType
from typing import Callable

from src.base import (
    BaseVisualizer, INPUT_QUIT, INPUT_LEFT, INPUT_RIGHT,
    INPUT_UP, INPUT_DOWN, INPUT_ENJOY, INPUT_SPACE,
    INPUT_FULLSCREEN, INPUT_ESCAPE, INPUT_REVERSE, HUD_ROWS,
)
from src.crash_report import (
    CrashReportResult,
    CrashReporter,
    DEFAULT_REPORTING,
    request_crash_reporting_consent,
)
from src.waves import WaveVisualizer
from src.galaxy import GalaxyVisualizer
from src.spiral import SpiralVisualizer
from src.dyson import DysonVisualizer
from src.aurora import AuroraVisualizer
from src.ember import EmberVisualizer
from src.ripple import RippleVisualizer
from src.zen import ZenVisualizer
from src.skyline import SkylineVisualizer


MODE_NAMES = ["waves", "galaxy", "spiral", "dyson", "aurora", "ember", "ripple", "zen", "skyline"]

# Onboarding hint fades after this many frames
HINT_FRAMES = 240

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


class TerminalSession:
    def __init__(
        self,
        request_stop: Callable[[], None],
        *,
        stdin=None,
        stdout=None,
    ):
        self.request_stop = request_stop
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout
        self.term_settings = None
        self.received_signal: int | None = None
        self._orig_handlers: dict[int, signal.Handlers] = {}
        self._cursor_hidden = False
        self._alt_screen = False

    def enter(self) -> None:
        self._write(BaseVisualizer.ANSI_ALT_SCREEN_ON)
        self._alt_screen = True
        self._write(BaseVisualizer.ANSI_HIDE_CURSOR)
        self._cursor_hidden = True
        self._set_cbreak_mode()
        self._install_signal_handler(signal.SIGINT)
        self._install_signal_handler(signal.SIGTERM)

    def restore(self) -> None:
        self._write(BaseVisualizer.ANSI_RESET)
        if self._cursor_hidden:
            self._write(BaseVisualizer.ANSI_SHOW_CURSOR)
            self._cursor_hidden = False
        if self._alt_screen:
            self._write(BaseVisualizer.ANSI_ALT_SCREEN_OFF)
            self._alt_screen = False
        self._restore_terminal_mode()
        self._restore_signal_handlers()

    def _set_cbreak_mode(self) -> None:
        try:
            self.term_settings = termios.tcgetattr(self.stdin)
            tty.setcbreak(self.stdin.fileno())
        except (termios.error, AttributeError, OSError, ValueError):
            self.term_settings = None

    def _restore_terminal_mode(self) -> None:
        if self.term_settings is None:
            return
        try:
            termios.tcsetattr(self.stdin, termios.TCSADRAIN, self.term_settings)
        except (termios.error, AttributeError, OSError, ValueError):
            pass
        finally:
            self.term_settings = None

    def _install_signal_handler(self, signum: int) -> None:
        try:
            self._orig_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, self._handle_signal)
        except (AttributeError, OSError, RuntimeError, ValueError):
            pass

    def _restore_signal_handlers(self) -> None:
        for signum, handler in self._orig_handlers.items():
            try:
                signal.signal(signum, handler)
            except (AttributeError, OSError, RuntimeError, ValueError):
                pass
        self._orig_handlers.clear()

    def _handle_signal(self, signum: int, frame: FrameType | None) -> None:
        self.received_signal = signum
        self.request_stop()

    def _write(self, value: str) -> None:
        try:
            self.stdout.write(value)
            self.stdout.flush()
        except (BrokenPipeError, OSError):
            pass


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
        depth: float = 0.22,
        drift: float = 0.75,
        arm_gap: int = 2,
        trail: int = 4,
        spread: float = 0.30,
        orbit_speed: float = 1.5,
        curtains: int = 5,
        shimmer: float = 1.5,
        density: int = 80,
        warmth: float = 1.5,
        sources: int = 2,
        wavelength: float = 4.0,
        rake_width: int = 3,
        zen_level: int = 4,
        skyline_city: int = 0,
        skyline_glow: int = 3,
        crash_reporting: str = DEFAULT_REPORTING,
        crash_report_dir: str | None = None,
    ):
        common = dict(size=size, speed=speed, brightness=brightness,
                      ascii_mode=ascii_mode, oneshot=oneshot)

        self.visualizers: list[BaseVisualizer] = [
            WaveVisualizer(**common, wave_count=wave_count, foam=foam),
            GalaxyVisualizer(**common, depth=depth, drift=drift),
            SpiralVisualizer(**common, arm_gap=arm_gap, trail=trail),
            DysonVisualizer(**common, spread=spread, orbit_speed=orbit_speed),
            AuroraVisualizer(**common, curtains=curtains, shimmer=shimmer),
            EmberVisualizer(**common, density=density, warmth=warmth),
            RippleVisualizer(**common, sources=sources, wavelength=wavelength),
            ZenVisualizer(**common, rake_width=rake_width, level=zen_level),
            SkylineVisualizer(**common, city=skyline_city, glow=skyline_glow),
        ]
        self.index = MODE_NAMES.index(start_mode) if start_mode in MODE_NAMES else 0
        self.fullscreen = False
        self.total_frames = 0  # tracks frames across mode switches for hint fade
        self.crash_reporting = crash_reporting
        self.crash_report_dir = crash_report_dir
        self._stop_requested = False
        self._terminal_session: TerminalSession | None = None

    @property
    def current(self) -> BaseVisualizer:
        return self.visualizers[self.index]

    def run(self) -> None:
        self._stop_requested = False
        github_opt_in = request_crash_reporting_consent(reporting=self.crash_reporting)
        reporter = CrashReporter.from_environment(
            reporting=self.crash_reporting,
            report_dir=self.crash_report_dir,
            github_opt_in=github_opt_in,
        )
        session = self._make_terminal_session()
        exc_info = None
        try:
            session.enter()
            while not self._stop_requested:
                vis = self.current
                vis._old_term_settings = session.term_settings
                vis.set_hud_rows(0 if self.fullscreen else HUD_ROWS)

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
            self._request_stop()
        except Exception:
            exc_info = sys.exc_info()
        finally:
            session.restore()
            for vis in self.visualizers:
                vis._old_term_settings = None

        if exc_info is not None:
            try:
                result = reporter.report_exception(exc_info, self._crash_context(session))
                self._print_crash_report_result(result)
            except Exception as report_error:  # noqa: BLE001 - terminal already recovered
                print(f"Freio crashed; crash reporting also failed: {report_error}", file=sys.stderr)
            raise SystemExit(1)

    def _make_terminal_session(self) -> TerminalSession:
        session = TerminalSession(self._request_stop)
        self._terminal_session = session
        return session

    def _request_stop(self) -> None:
        self._stop_requested = True
        for vis in self.visualizers:
            vis.running = False

    def _crash_context(self, session: TerminalSession) -> dict:
        cols, rows = self.current._get_terminal_size()
        return {
            "mode": MODE_NAMES[self.index],
            "visualizer": type(self.current).__name__,
            "frame": self.current.frame,
            "total_frames": self.total_frames,
            "fullscreen": self.fullscreen,
            "terminal": {"columns": cols, "rows": rows},
            "signal": session.received_signal,
        }

    def _print_crash_report_result(self, result: CrashReportResult) -> None:
        print("Freio crashed, but the terminal was restored.", file=sys.stderr)
        if result.path is not None:
            print(f"Crash report saved: {result.path}", file=sys.stderr)
        if result.github_status == "reported" and result.github_url:
            print(f"GitHub issue updated: {result.github_url}", file=sys.stderr)
        elif result.github_status == "awaiting_opt_in":
            print("GitHub issue submission skipped: crash reporting opt-in is not enabled.", file=sys.stderr)
        elif result.github_status == "not_configured":
            print(
                "GitHub issue submission skipped: set FREIO_GITHUB_REPO and FREIO_GITHUB_TOKEN.",
                file=sys.stderr,
            )
        elif result.github_status == "failed":
            print(f"GitHub issue submission failed: {result.error}", file=sys.stderr)

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
        elif event in (INPUT_ENJOY, INPUT_FULLSCREEN):
            self._set_fullscreen(not self.fullscreen)
        elif event == INPUT_ESCAPE and self.fullscreen:
            self._set_fullscreen(False)
        elif event == INPUT_REVERSE:
            vis.reverse()
        return True

    def _draw_hud(self) -> str:
        self.total_frames += 1

        if self.fullscreen:
            return ""

        try:
            cols = os.get_terminal_size().columns
            rows = os.get_terminal_size().lines
        except OSError:
            cols, rows = 80, 24
        cols = max(1, cols)
        rows = max(1, rows)

        if rows <= HUD_ROWS or cols < 12:
            return ""

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
            val_str = s.format_value(val)
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
                hint_str = (
                    f"{hint_color}space next   "
                    f"\u2190\u2192 {vis.sliders[0].name.lower() if vis.sliders else ''}   "
                    f"\u2191\u2193 {vis.sliders[1].name.lower() if len(vis.sliders) > 1 else ''}   "
                    f"f fullscreen   e enjoy   r reverse   q quit\033[0m"
                )

        # Layout: 3 lines at bottom (separator, sliders, mode)
        # Optional 4th line for hint
        slider_plain_len = len(_ANSI_RE.sub("", hud_sliders))
        pad_s = max(1, (cols - slider_plain_len) // 2 + 1)
        pad_m = max(1, (cols - len(mode_str)) // 2 + 1)

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
            pad_h = max(1, (cols - hint_plain_len) // 2 + 1)
            y_hint = y_sep - 1
            if y_hint >= 1:
                out.append(f"\033[{y_hint};1H\033[2K\033[{y_hint};{pad_h}H{hint_str}")

        return "".join(out)

    def _set_fullscreen(self, fullscreen: bool) -> None:
        if self.fullscreen == fullscreen:
            return
        self.fullscreen = fullscreen
        hud_rows = 0 if fullscreen else HUD_ROWS
        for vis in self.visualizers:
            vis.set_hud_rows(hud_rows)
