import math
import random

from src.base import BaseVisualizer, Slider, CHAR_ASPECT


class RippleVisualizer(BaseVisualizer):
    """Concentric ripples — expanding rings with interference patterns."""

    CHARS = {
        "peak":   "\u2588",   # █
        "heavy":  "\u2593",   # ▓
        "medium": "\u2592",   # ▒
        "light":  "\u2591",   # ░
        "dim":    "\u00b7",   # ·
        "peak_ascii":   "#",
        "heavy_ascii":  "%",
        "medium_ascii": "=",
        "light_ascii":  "-",
        "dim_ascii":    ".",
    }

    sliders = [
        Slider(name="Sources", attr="sources", min_val=1, max_val=5, step=1, fmt="d"),
        Slider(name="Wavelength", attr="wavelength", min_val=2.0, max_val=8.0, step=0.5),
    ]

    # Trough dimming: crests are brighter than troughs
    _DIM_MAP = {"97": "96", "96": "36", "36": "34", "34": "2;34"}

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
                "cx_freq": 0.01 + random.random() * 0.02,
                "cy_freq": 0.01 + random.random() * 0.02,
                "cx_phase": random.random() * math.pi * 2,
                "cy_phase": random.random() * math.pi * 2,
                "cx_amp": 0.15 + random.random() * 0.20,
                "cy_amp": 0.15 + random.random() * 0.20,
            })

    def _get_char(self, name: str) -> str:
        if self.ascii_mode:
            key = f"{name}_ascii"
            return self.CHARS.get(key, self.CHARS.get(name, " "))
        return self.CHARS.get(name, " ")

    def _color(self, code: str) -> str:
        return f"\033[{code}m"

    def render_frame(self) -> str:
        w, h = self.width, self.height
        n = int(self.sources)
        dim = self.brightness < 50
        bright_ok = self.brightness >= 100
        freq = 2.0 * math.pi / self.wavelength
        inv_sqrt_n = 1.0 / math.sqrt(n)

        # Compute source positions (Lissajous drift)
        src_pos = []
        half_w = w / 2.0
        half_h = h / 2.0
        for i in range(n):
            sp = self.source_params[i]
            sx = half_w + sp["cx_amp"] * half_w * math.sin(
                self.frame * sp["cx_freq"] + sp["cx_phase"]
            )
            sy = half_h + sp["cy_amp"] * half_h * math.sin(
                self.frame * sp["cy_freq"] + sp["cy_phase"]
            )
            src_pos.append((sx, sy))

        lines = []
        for y in range(h):
            row = []
            for x in range(w):
                total = 0.0
                for sx, sy in src_pos:
                    dx = x - sx
                    dy = (y - sy) / CHAR_ASPECT
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist < 0.5:
                        dist = 0.5
                    wave = math.sin(dist * freq - self.frame * 0.12)
                    damping = min(2.0, 1.0 / math.sqrt(dist))
                    total += wave * damping

                amplitude = total * inv_sqrt_n
                abs_amp = abs(amplitude)

                if abs_amp < 0.08:
                    row.append(" ")
                    continue

                # Character by amplitude
                if abs_amp > 1.0:
                    char = self._get_char("peak")
                elif abs_amp > 0.7:
                    char = self._get_char("heavy")
                elif abs_amp > 0.4:
                    char = self._get_char("medium")
                elif abs_amp > 0.2:
                    char = self._get_char("light")
                else:
                    char = self._get_char("dim")

                # Color by amplitude
                if abs_amp > 1.0:
                    code = "97" if bright_ok else "96"
                elif abs_amp > 0.7:
                    code = "96" if bright_ok else "36"
                elif abs_amp > 0.4:
                    code = "36"
                elif abs_amp > 0.2:
                    code = "34"
                else:
                    code = "2;34"

                # Troughs are dimmer
                if amplitude < 0:
                    code = self._DIM_MAP.get(code, code)

                if dim and not code.startswith("2;"):
                    code = f"2;{code}"

                row.append(f"{self._color(code)}{char}{self.ANSI_RESET}")

            lines.append("".join(row))

        return "\n".join(lines) + f"\n\033[{h + 1};1H"
