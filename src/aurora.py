import math
import random

from src.base import BaseVisualizer, Slider, CHAR_ASPECT


class AuroraVisualizer(BaseVisualizer):
    """Northern lights — shimmering vertical curtains of color."""

    CHARS = {
        "bright":     "\u2588",   # █
        "heavy":      "\u2593",   # ▓
        "medium":     "\u2592",   # ▒
        "light":      "\u2591",   # ░
        "dim":        "\u00b7",   # ·
        "star":       "\u00b7",   # ·
        "bright_ascii": "#",
        "heavy_ascii":  "%",
        "medium_ascii": "=",
        "light_ascii":  "-",
        "dim_ascii":    ".",
        "star_ascii":   ".",
    }

    sliders = [
        Slider(name="Curtains", attr="curtains", min_val=3, max_val=8, step=1, fmt="d"),
        Slider(name="Shimmer", attr="shimmer", min_val=0.5, max_val=3.0, step=0.25),
    ]

    def __init__(
        self,
        size: int = 0,
        speed: int = 5,
        brightness: int = 100,
        ascii_mode: bool = False,
        oneshot: bool = False,
        curtains: int = 5,
        shimmer: float = 1.5,
    ):
        super().__init__(size, speed, brightness, ascii_mode, oneshot)
        self.curtains = curtains
        self.shimmer = shimmer
        self.stars = self._generate_stars()

    def _on_resize(self) -> None:
        self.stars = self._generate_stars()

    def _generate_stars(self) -> dict[tuple[int, int], float]:
        stars = {}
        random.seed(88)
        for y in range(self.height):
            for x in range(self.width):
                if random.random() < 0.012:
                    stars[(y, x)] = random.random()
        return stars

    def _get_char(self, name: str) -> str:
        if self.ascii_mode:
            key = f"{name}_ascii"
            return self.CHARS.get(key, self.CHARS.get(name, " "))
        return self.CHARS.get(name, " ")

    def _color(self, code: str) -> str:
        return f"\033[{code}m"

    def _curtain_color(self, vert_ratio: float, intense: bool) -> str:
        """Color by vertical position. vert_ratio: 0=top, 1=bottom."""
        dim = self.brightness < 50

        if vert_ratio < 0.15:
            code = "35" if (dim or not intense) else "95"
        elif vert_ratio < 0.40:
            code = "34" if (dim or not intense) else "94"
        elif vert_ratio < 0.70:
            code = "36" if (dim or not intense) else "96"
        else:
            code = "32" if (dim or not intense) else "92"

        if dim:
            code = f"2;{code}"
        return self._color(code)

    def render_frame(self) -> str:
        w, h = self.width, self.height
        n = int(self.curtains)

        # Pre-compute curtain center x-positions for this frame
        curtain_xs = []
        for i in range(n):
            base_x = (i + 1) * w / (n + 1)
            sway = (
                self.shimmer * 4.0 * math.sin(self.frame * 0.04 + i * 1.7)
                + self.shimmer * 1.5 * math.sin(self.frame * 0.11 + i * 3.1)
                + self.shimmer * 0.5 * math.sin(self.frame * 0.23 + i * 0.9)
            )
            curtain_xs.append(base_x + sway)

        star_char = self._get_char("star")
        lines = []

        for y in range(h):
            row = []
            vert_ratio = y / max(1, h - 1)
            # Vertical taper: curtains are widest at mid-height, thin at top/bottom
            taper = 0.3 + 0.7 * math.sin(vert_ratio * math.pi)

            for x in range(w):
                # Find max intensity across all curtains
                best_intensity = 0.0
                for i, cx in enumerate(curtain_xs):
                    dx = abs(x - cx)
                    half_w = 3.0 * taper
                    if dx < half_w:
                        raw = (1.0 - dx / half_w) ** 1.5
                        # Per-cell shimmer modulation
                        shimmer_mod = 0.7 + 0.3 * math.sin(
                            y * 0.3 + self.frame * 0.15 + i * 2.0
                        )
                        best_intensity = max(best_intensity, raw * shimmer_mod)

                if best_intensity > 0.05:
                    # Map intensity to character
                    if best_intensity > 0.8:
                        char = self._get_char("bright")
                    elif best_intensity > 0.6:
                        char = self._get_char("heavy")
                    elif best_intensity > 0.4:
                        char = self._get_char("medium")
                    elif best_intensity > 0.2:
                        char = self._get_char("light")
                    else:
                        char = self._get_char("dim")

                    intense = best_intensity > 0.6
                    color = self._curtain_color(vert_ratio, intense)
                    row.append(f"{color}{char}{self.ANSI_RESET}")
                elif (y, x) in self.stars:
                    seed = self.stars[(y, x)]
                    sc = "90" if seed > 0.92 else "2;90"
                    row.append(f"{self._color(sc)}{star_char}{self.ANSI_RESET}")
                else:
                    row.append(" ")

            lines.append("".join(row))

        return "\n".join(lines) + f"\033[{h + 1};1H"
