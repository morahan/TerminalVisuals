import math
import random

from src.base import BaseVisualizer, Slider


class EmberVisualizer(BaseVisualizer):
    """Rising embers — warm particles drifting upward with pulse and wobble."""

    CHARS = {
        "peak":       "\u25cf",   # ●
        "bright":     "\u25c6",   # ◆
        "medium":     "\u2022",   # •
        "dim":        "\u00b7",   # ·
        "glow_heavy": "\u2593",   # ▓
        "glow_mid":   "\u2592",   # ▒
        "glow_light": "\u2591",   # ░
        "peak_ascii":       "O",
        "bright_ascii":     "*",
        "medium_ascii":     "o",
        "dim_ascii":        ".",
        "glow_heavy_ascii": "#",
        "glow_mid_ascii":   "=",
        "glow_light_ascii": "-",
    }

    sliders = [
        Slider(name="Density", attr="density", min_val=20, max_val=200, step=10, fmt="d"),
        Slider(name="Warmth", attr="warmth", min_val=0.5, max_val=3.0, step=0.25),
    ]

    def __init__(
        self,
        size: int = 0,
        speed: int = 5,
        brightness: int = 100,
        ascii_mode: bool = False,
        oneshot: bool = False,
        density: int = 80,
        warmth: float = 1.5,
    ):
        super().__init__(size, speed, brightness, ascii_mode, oneshot)
        self.density = density
        self.warmth = warmth
        self._seed_particles()

    def _seed_particles(self) -> None:
        random.seed(55)
        self.particles = []
        for _ in range(200):
            self.particles.append({
                "base_x": random.random(),
                "rise_speed": 0.3 + random.random() * 0.7,
                "y_offset": random.random(),
                "wobble_freq": 0.5 + random.random() * 1.5,
                "wobble_amp": 0.5 + random.random() * 2.0,
                "wobble_phase": random.random() * math.pi * 2,
                "pulse_freq": 0.3 + random.random() * 0.6,
                "pulse_phase": random.random() * math.pi * 2,
                "size_seed": random.random(),
            })

    def _get_char(self, name: str) -> str:
        if self.ascii_mode:
            key = f"{name}_ascii"
            return self.CHARS.get(key, self.CHARS.get(name, " "))
        return self.CHARS.get(name, " ")

    def _color(self, code: str) -> str:
        return f"\033[{code}m"

    def _particle_style(self, combined: float) -> tuple[str, str]:
        """Return (char, color_code) for a particle at given brightness."""
        dim = self.brightness < 50
        warm_shift = (self.warmth - 1.5) * 0.15

        # Character by brightness
        if combined > 0.8:
            char = self._get_char("peak")
        elif combined > 0.55:
            char = self._get_char("bright")
        elif combined > 0.3:
            char = self._get_char("medium")
        else:
            char = self._get_char("dim")

        # Color by brightness + warmth
        if combined > 0.85 + warm_shift and self.brightness >= 100:
            code = "97"
        elif combined > 0.65 + warm_shift:
            code = "93"
        elif combined > 0.4 + warm_shift:
            code = "33"
        elif combined > 0.2 + warm_shift:
            code = "31"
        else:
            code = "2;31"

        if dim and not code.startswith("2;"):
            code = f"2;{code}"

        return char, self._color(code)

    def render_frame(self) -> str:
        w, h = self.width, self.height
        grid: list[list[str]] = [[" " for _ in range(w)] for _ in range(h)]

        # Ground glow (bottom rows)
        ground_rows = min(3, max(1, h // 6))
        for gy in range(h - ground_rows, h):
            depth = h - gy  # 1=bottom, 2, 3
            for gx in range(w):
                glow_val = 0.5 + 0.5 * math.sin(gx * 0.15 + self.frame * 0.06)
                if glow_val < 0.3:
                    continue
                if depth == 1:
                    char = self._get_char("glow_heavy")
                    code = "2;33" if self.brightness < 50 else "33"
                elif depth == 2:
                    char = self._get_char("glow_mid")
                    code = "2;31" if self.brightness < 50 else "31"
                else:
                    char = self._get_char("glow_light")
                    code = "2;31"
                grid[gy][gx] = f"{self._color(code)}{char}{self.ANSI_RESET}"

        # Particles
        count = int(self.density)
        for idx in range(min(count, len(self.particles))):
            p = self.particles[idx]

            # Vertical: rises upward, wraps
            y_norm = (1.0 - (self.frame * 0.008 * p["rise_speed"] + p["y_offset"])) % 1.0
            y = int(y_norm * (h - ground_rows))
            if y < 0 or y >= h - ground_rows:
                continue

            # Horizontal: base + wobble
            wobble = math.sin(
                self.frame * 0.05 * p["wobble_freq"] + p["wobble_phase"]
            ) * p["wobble_amp"]
            x = int(p["base_x"] * w + wobble) % w

            # Brightness pulse
            raw_pulse = math.sin(self.frame * 0.04 * p["pulse_freq"] + p["pulse_phase"])
            brightness_val = raw_pulse * raw_pulse
            combined = brightness_val * (0.5 + 0.5 * p["size_seed"])

            if combined < 0.05:
                continue

            char, color = self._particle_style(combined)
            grid[y][x] = f"{color}{char}{self.ANSI_RESET}"

        lines = []
        for row in grid:
            lines.append("".join(row))
        return "\n".join(lines) + f"\033[{h + 1};1H"
