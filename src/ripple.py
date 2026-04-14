import math
import random

from src.base import BaseVisualizer, Slider, CHAR_ASPECT


class RippleVisualizer(BaseVisualizer):
    """Minimal interference garden -- thin iridescent ripples with slow orbital drift."""

    CHARS = {
        "peak":   "\u25cf",   # ●
        "heavy":  "\u2022",   # •
        "medium": "\u25e6",   # ◦
        "dim":    "\u00b7",   # ·
        "peak_ascii":   "@",
        "heavy_ascii":  "o",
        "medium_ascii": ".",
        "dim_ascii":    ".",
    }

    sliders = [
        Slider(name="Sources", attr="sources", min_val=1, max_val=5, step=1, fmt="d"),
        Slider(name="Wavelength", attr="wavelength", min_val=2.0, max_val=8.0, step=0.5),
    ]

    _BRIGHT_PALETTE = ("2;34", "34", "36", "96", "97", "93", "91", "95")
    _DIM_PALETTE = ("2;34", "2;34", "2;36", "36", "37", "2;33", "33", "35")

    def __init__(
        self,
        size: int = 0,
        speed: int = 5,
        brightness: int = 100,
        ascii_mode: bool = False,
        oneshot: bool = False,
        sources: int = 2,
        wavelength: float = 4.0,
    ):
        super().__init__(size, speed, brightness, ascii_mode, oneshot)
        self.sources = sources
        self.wavelength = wavelength
        self._seed_sources()

    def _seed_sources(self) -> None:
        random.seed(63)
        self.source_params = []
        for _ in range(5):
            self.source_params.append({
                "orbit_jitter": random.random() * math.pi * 2,
                "cx_phase": random.random() * math.pi * 2,
                "cy_phase": random.random() * math.pi * 2,
                "cx_amp": 0.04 + random.random() * 0.05,
                "cy_amp": 0.03 + random.random() * 0.05,
            })

    def _get_char(self, name: str) -> str:
        if self.ascii_mode:
            key = f"{name}_ascii"
            return self.CHARS.get(key, self.CHARS.get(name, " "))
        return self.CHARS.get(name, " ")

    def _color(self, code: str) -> str:
        return f"\033[{code}m"

    def _source_positions(self, w: int, h: int, n: int) -> list[tuple[float, float]]:
        cx = w / 2.0
        cy = h / 2.0
        radial_limit = min(w * 0.30, h / CHAR_ASPECT * 0.24)
        t = self.frame

        if n == 1:
            sp = self.source_params[0]
            sx = cx + math.cos(t * 0.025 + sp["cx_phase"]) * radial_limit * 0.18
            sy = cy + math.sin(t * 0.018 + sp["cy_phase"]) * radial_limit * 0.10 * CHAR_ASPECT
            return [(sx, sy)]

        positions = []
        base_angle = t * 0.018
        breathe = 0.72 + 0.10 * math.sin(t * 0.010)
        for i in range(n):
            sp = self.source_params[i]
            angle = base_angle + (2.0 * math.pi * i / n)
            angle += 0.18 * math.sin(t * 0.012 + sp["orbit_jitter"])
            radius = radial_limit * breathe * (0.90 + 0.08 * math.cos(t * 0.017 + i * 1.3))
            sx = cx + math.cos(angle) * radius
            sy = cy + math.sin(angle) * radius * CHAR_ASPECT * 0.85
            sx += math.sin(t * 0.030 + sp["cx_phase"]) * w * sp["cx_amp"]
            sy += math.cos(t * 0.026 + sp["cy_phase"]) * h * sp["cy_amp"] * 0.5
            positions.append((sx, sy))

        return positions

    def _pick_char(self, energy: float) -> str:
        if energy > 0.82:
            return self._get_char("peak")
        if energy > 0.52:
            return self._get_char("heavy")
        if energy > 0.28:
            return self._get_char("medium")
        return self._get_char("dim")

    def _pick_color(self, hue: float, energy: float, vignette: float) -> str:
        palette = self._DIM_PALETTE if self.brightness < 50 else self._BRIGHT_PALETTE
        idx = min(len(palette) - 1, max(0, int(hue * len(palette))))
        code = palette[idx]

        if energy > 0.92 and self.brightness >= 75:
            return "97;1"
        if energy < 0.20 and vignette < 0.30:
            return "2;34"
        return code

    def render_frame(self) -> str:
        w, h = self.width, self.height
        n = int(self.sources)
        freq = 2.0 * math.pi / self.wavelength
        inv_sqrt_n = 1.0 / math.sqrt(max(1, n))
        src_pos = self._source_positions(w, h, n)
        cx = w / 2.0
        cy = h / 2.0
        max_radius = math.sqrt((w / 2.0) ** 2 + (h / CHAR_ASPECT / 2.0) ** 2)
        t = self.frame

        lines = []
        for y in range(h):
            row = []
            for x in range(w):
                total = 0.0
                contour = 0.0
                hue_mix = 0.0
                for i, (sx, sy) in enumerate(src_pos):
                    dx = x - sx
                    dy = (y - sy) / CHAR_ASPECT
                    dist = math.sqrt(dx * dx + dy * dy)
                    dist = max(0.5, dist)

                    phase = dist * freq - t * 0.12 + i * 0.9
                    phase += 0.55 * math.sin(dist * 0.16 - t * 0.035 + i * 1.2)

                    wave = math.sin(phase)
                    damping = 1.0 / (1.0 + 0.16 * dist)
                    total += wave * damping
                    contour += ((0.5 + 0.5 * math.cos(phase)) ** 12) * damping
                    hue_mix += math.sin(phase * 0.7 + i * 1.6) * damping

                amplitude = total * inv_sqrt_n
                line_strength = contour / max(1, n)
                dist_center = math.sqrt((x - cx) ** 2 + ((y - cy) / CHAR_ASPECT) ** 2)
                vignette = max(0.0, 1.0 - (dist_center / max_radius) ** 1.85)
                energy = (line_strength * 0.95 + abs(amplitude) * 0.28) * (0.30 + 0.70 * vignette)

                if energy < 0.10:
                    row.append(" ")
                    continue

                hue = 0.5 + 0.5 * math.sin(hue_mix * 1.2 + amplitude * 1.5 + t * 0.03)
                code = self._pick_color(hue, energy, vignette)
                char = self._pick_char(energy)

                row.append(f"{self._color(code)}{char}{self.ANSI_RESET}")

            lines.append("".join(row))

        return "\n".join(lines) + f"\033[{h + 1};1H"
