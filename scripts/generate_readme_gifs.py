#!/usr/bin/env python3
"""Build README demo GIFs from Freio's real ANSI renderers.

Requires ImageMagick (`magick`) and Inkscape (`inkscape`), but no Python
packages. Run from the project root with `python scripts/generate_readme_gifs.py`
after changing a visualizer.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.aurora import AuroraVisualizer
from src.dyson import DysonVisualizer
from src.ember import EmberVisualizer
from src.galaxy import GalaxyVisualizer
from src.ripple import RippleVisualizer
from src.skyline import SkylineVisualizer
from src.spiral import SpiralVisualizer
from src.waves import WaveVisualizer
from src.zen import ZenVisualizer


OUTPUT_DIR = ROOT / "assets" / "demos"
ANSI_SGR = re.compile(r"\x1b\[([0-9;]*)m")
ANSI_CURSOR = re.compile(r"\x1b\[[0-9;]*[Hf]")

DEFAULT_COLOR = "#d6deeb"
ANSI_COLORS = {
    30: "#151923", 31: "#ff6b6b", 32: "#74e8a5", 33: "#ffd166",
    34: "#78a9ff", 35: "#e599f7", 36: "#63e6ff", 37: "#d6deeb",
    90: "#6e7681", 91: "#ff8787", 92: "#8ce99a", 93: "#ffe066",
    94: "#91b4ff", 95: "#f0abfc", 96: "#8be9fd", 97: "#ffffff",
}


class Demo:
    def __init__(
        self,
        command: str,
        make_visualizer: Callable[[], object],
        frame_offset: float = 0.0,
    ):
        self.command = command
        self.make_visualizer = make_visualizer
        self.frame_offset = frame_offset


DEMOS = {
    "waves": Demo("freio --mode waves", lambda: WaveVisualizer(size=72, wave_count=4)),
    "galaxy": Demo("freio --mode galaxy --depth 0.75 --drift 1.5", lambda: GalaxyVisualizer(size=72, depth=0.75, drift=1.5)),
    "spiral": Demo("freio --mode spiral --arm-gap 1 --trail 7", lambda: SpiralVisualizer(size=72, arm_gap=1, trail=7), frame_offset=90.0),
    "dyson": Demo("freio --mode dyson --orbit-speed 2", lambda: DysonVisualizer(size=72, orbit_speed=2.0), frame_offset=800.0),
    "aurora": Demo("freio --mode aurora --curtains 6 --shimmer 2", lambda: AuroraVisualizer(size=72, curtains=6, shimmer=2.0)),
    "ember": Demo("freio --mode ember --density 120 --warmth 2", lambda: EmberVisualizer(size=72, density=120, warmth=2.0)),
    "ripple": Demo("freio --mode ripple --sources 3 --wavelength 5", lambda: RippleVisualizer(size=72, sources=3, wavelength=5.0)),
    "zen": Demo("freio --mode zen --rake-width 4 --zen-level 5", lambda: ZenVisualizer(size=72, rake_width=4, level=5), frame_offset=180.0),
    "skyline": Demo("freio --mode skyline --skyline-city tokyo --skyline-glow 4", lambda: SkylineVisualizer(size=72, city=4, glow=4, time_source=lambda: 0.0)),
}


def ansi_spans(line: str) -> list[tuple[str, str]]:
    """Convert a line with SGR color codes into (text, color) spans."""
    spans: list[tuple[str, str]] = []
    color = DEFAULT_COLOR
    cursor = 0

    def add(text: str) -> None:
        if not text:
            return
        if spans and spans[-1][1] == color:
            spans[-1] = (spans[-1][0] + text, color)
        else:
            spans.append((text, color))

    for match in ANSI_SGR.finditer(line):
        add(line[cursor:match.start()])
        values = [int(value) for value in match.group(1).split(";") if value] or [0]
        for value in values:
            if value == 0:
                color = DEFAULT_COLOR
            elif value in ANSI_COLORS:
                color = ANSI_COLORS[value]
        cursor = match.end()
    add(line[cursor:])
    return spans


def visible_lines(frame: str) -> list[str]:
    lines = [ANSI_CURSOR.sub("", line) for line in frame.splitlines()]
    while lines and not ANSI_SGR.sub("", lines[-1]).strip():
        lines.pop()
    return lines


def frame_svg(lines: list[str], command: str) -> str:
    plain_width = max(1, max((len(ANSI_SGR.sub("", line)) for line in lines), default=1))
    canvas_width, canvas_height = 840, 480
    font_size = min(14.5, 760 / plain_width * 1.55)
    char_width = font_size / 1.55
    line_height = font_size * 1.20
    content_width = plain_width * char_width
    content_height = len(lines) * line_height
    terminal_width = min(canvas_width - 32, max(content_width + 48, 420))
    terminal_height = min(canvas_height - 28, max(content_height + 76, 180))
    terminal_left = (canvas_width - terminal_width) / 2
    terminal_top = (canvas_height - terminal_height) / 2
    text_left = terminal_left + (terminal_width - content_width) / 2
    text_top = terminal_top + 52 + max(0, (terminal_height - 70 - content_height) / 2)

    text_nodes = []
    for row, line in enumerate(lines):
        x = text_left
        y = text_top + (row + 1) * line_height
        for text, color in ansi_spans(line):
            text_nodes.append(
                f'<text x="{x:.2f}" y="{y:.2f}" fill="{color}">{escape(text)}</text>'
            )
            x += len(text) * char_width

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_width}" height="{canvas_height}" viewBox="0 0 {canvas_width} {canvas_height}">
  <rect width="100%" height="100%" fill="#0b0f17"/>
  <rect x="{terminal_left:.2f}" y="{terminal_top:.2f}" width="{terminal_width:.2f}" height="{terminal_height:.2f}" rx="14" fill="#0e131d" stroke="#2a3444"/>
  <path d="M {terminal_left + 14:.2f} {terminal_top + 36:.2f} H {terminal_left + terminal_width - 14:.2f}" stroke="#2a3444"/>
  <circle cx="{terminal_left + 20:.2f}" cy="{terminal_top + 18:.2f}" r="5" fill="#ff6b6b"/>
  <circle cx="{terminal_left + 38:.2f}" cy="{terminal_top + 18:.2f}" r="5" fill="#ffd166"/>
  <circle cx="{terminal_left + 56:.2f}" cy="{terminal_top + 18:.2f}" r="5" fill="#74e8a5"/>
  <text x="{terminal_left + 76:.2f}" y="{terminal_top + 23:.2f}" fill="#8b9bb4" font-family="Menlo, Monaco, 'DejaVu Sans Mono', monospace" font-size="13">{escape(command)}</text>
  <g font-family="Menlo, Monaco, 'DejaVu Sans Mono', monospace" font-size="{font_size:.2f}" xml:space="preserve">{''.join(text_nodes)}</g>
</svg>'''


def render_demo(name: str, demo: Demo, frames: int) -> None:
    visualizer = demo.make_visualizer()
    # A wide terminal makes the demos easy to read in the README while keeping
    # the renderer's exact animation logic intact.
    visualizer.width, visualizer.height = 72, 24
    visualizer.auto_size = False
    visualizer._on_resize()

    with tempfile.TemporaryDirectory(prefix=f"freio-{name}-") as temp_dir:
        temp_path = Path(temp_dir)
        png_paths = []
        inkscape = shutil.which("inkscape")
        assert inkscape is not None
        for index in range(frames):
            visualizer.frame = demo.frame_offset + index * 3.2
            if name == "skyline":
                visualizer._time_source = lambda value=index * 0.85: value
            svg_path = temp_path / f"{index:03}.svg"
            png_path = temp_path / f"{index:03}.png"
            svg_path.write_text(frame_svg(visible_lines(visualizer.render_frame()), demo.command))
            subprocess.run(
                [inkscape, str(svg_path), f"--export-filename={png_path}"],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            png_paths.append(png_path)

        output = OUTPUT_DIR / f"{name}.gif"
        subprocess.run(
            ["magick", "-delay", "10", "-loop", "0", *map(str, png_paths), "-layers", "Optimize", str(output)],
            check=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate README demonstration GIFs.")
    parser.add_argument("modes", nargs="*", choices=sorted(DEMOS), help="Only generate these modes")
    parser.add_argument("--frames", type=int, default=18, help="Frames per GIF (default: 18)")
    args = parser.parse_args()

    missing = [tool for tool in ("magick", "inkscape") if shutil.which(tool) is None]
    if missing:
        raise SystemExit(f"Missing required tools: {', '.join(missing)}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in args.modes or DEMOS.keys():
        render_demo(name, DEMOS[name], args.frames)
        print(f"wrote {OUTPUT_DIR / f'{name}.gif'}")


if __name__ == "__main__":
    main()
