import math
import random

from src.base import BaseVisualizer, Slider, CHAR_ASPECT


class MinimalismVisualizer(BaseVisualizer):
    """Edge-on galaxy disc — single box-drawing character per row, damped settle."""

    CHARS = {
        "edge": "\u2502",       # │
        "edge_ascii": "|",
        "core": "\u2503",       # ┃
        "core_ascii": "|",
        "star": "\u00b7",       # ·
        "star_ascii": ".",
    }

    sliders = [
        Slider(name="Depth", attr="depth", min_val=0.10, max_val=0.50, step=0.05, fmt=".2f"),
        Slider(name="Drift", attr="drift", min_val=0.5, max_val=3.0, step=0.25),
    ]

    def __init__(
        self,
        size: int = 0,
        speed: int = 5,
        brightness: int = 100,
        ascii_mode: bool = False,
        oneshot: bool = False,
        depth: float = 0.20,
        drift: float = 1.5,
    ):
        super().__init__(size, speed, brightness, ascii_mode, oneshot)
        self.depth = depth
        self.drift = drift
        self.stars = self._generate_stars()

    def _on_resize(self) -> None:
        self.stars = self._generate_stars()

    def _generate_stars(self) -> dict[tuple[int, int], float]:
        stars = {}
        random.seed(77)
        for y in range(self.height):
            for x in range(self.width):
                if random.random() < 0.015:
                    stars[(y, x)] = random.random()
        return stars

    def _get_char(self, name: str) -> str:
        if self.ascii_mode:
            key = f"{name}_ascii"
            return self.CHARS.get(key, self.CHARS.get(name, " "))
        return self.CHARS.get(name, " ")

    def _color(self, code: str) -> str:
        return f"\033[{code}m"

    def _compute_angles(self) -> tuple[float, float]:
        cycle = 300
        t = self.frame % cycle
        progress = t / cycle

        # Alpha: damped single-arc deceleration (disc breathes thinner→wider→settle)
        # One smooth arc that decelerates — no direction reversals
        amplitude = 0.10 * self.drift

        # Smooth ramp: rises in first 20%, decays over remaining 80%
        if progress < 0.20:
            # Ease-in with sine curve (0 → 1)
            arc = math.sin(progress / 0.20 * math.pi / 2)
        else:
            # Ease-out decay (1 → ~0)
            decay_progress = (progress - 0.20) / 0.80
            arc = math.cos(decay_progress * math.pi / 2)

        alpha = self.depth + amplitude * arc

        # Residual micro-breathing so the settled state is alive
        alpha += 0.006 * math.sin(self.frame * 0.011)

        # Beta: glacial continuous drift — no oscillation, no reversal
        # Barely perceptible lateral creep using the global frame counter
        beta = 0.012 * math.sin(self.frame * 0.003) + 0.004 * math.sin(self.frame * 0.007)

        # Clamp alpha so the disc never thins below 65% of resting depth
        alpha = max(self.depth * 0.65, alpha)
        return alpha, beta

    def _rim_x_positions(
        self, y_row: int, cy: float, cx: float, R: float, alpha: float, beta: float
    ) -> list[tuple[int, float]]:
        dy = y_row - cy
        sin_a = math.sin(alpha)
        cos_a = math.cos(alpha)
        sin_b = math.sin(beta)
        cos_b = math.cos(beta)

        if abs(sin_a) < 1e-6:
            return []

        sin_theta = -dy / (R * sin_a * CHAR_ASPECT)
        if abs(sin_theta) > 1.0:
            return []

        theta1 = math.asin(sin_theta)
        theta2 = math.pi - theta1

        results = []
        seen_cols = set()
        for theta in (theta1, theta2):
            x_screen = R * math.cos(theta) * cos_b + R * math.sin(theta) * cos_a * sin_b
            col = int(round(cx + x_screen))
            if 0 <= col < self.width and col not in seen_cols:
                norm_dist = min(1.0, abs(dy) / max(1, R * abs(sin_a) * CHAR_ASPECT))
                results.append((col, norm_dist))
                seen_cols.add(col)

        return results

    def _style_rim_point(self, norm_dist: float) -> tuple[str, str]:
        dim = self.brightness < 50

        if norm_dist < 0.20:
            # Core bulge — bright, heavy stroke
            char = self._get_char("core")
            color = self._color("37") if dim else self._color("96;1")
        elif norm_dist < 0.45:
            # Inner disc — white, clean
            char = self._get_char("edge")
            color = self._color("90") if dim else self._color("37")
        elif norm_dist < 0.75:
            # Mid disc — dimming
            char = self._get_char("edge")
            color = self._color("2;90") if dim else self._color("90")
        else:
            # Outer disc — barely there
            char = self._get_char("edge")
            color = self._color("2;90") if dim else self._color("2;37")

        return char, color

    def _star_color(self, seed: float) -> str:
        if self.brightness < 50:
            return self._color("2;90")
        if seed > 0.92:
            return self._color("90")
        return self._color("2;90")

    def render_frame(self) -> str:
        cx = self.width / 2.0
        cy = self.height / 2.0
        R = min(self.width * 0.42, self.height / CHAR_ASPECT * 0.42)

        alpha, beta = self._compute_angles()

        # Collect rim positions
        rim_cells: dict[tuple[int, int], tuple[str, str]] = {}
        for y in range(self.height):
            for col, norm_dist in self._rim_x_positions(y, cy, cx, R, alpha, beta):
                rim_cells[(y, col)] = self._style_rim_point(norm_dist)

        # Build output
        lines = []
        star_char = self._get_char("star")
        for y in range(self.height):
            row = []
            for x in range(self.width):
                if (y, x) in rim_cells:
                    char, color = rim_cells[(y, x)]
                    row.append(f"{color}{char}{self.ANSI_RESET}")
                elif (y, x) in self.stars:
                    row.append(f"{self._star_color(self.stars[(y, x)])}{star_char}{self.ANSI_RESET}")
                else:
                    row.append(" ")
            lines.append("".join(row))

        return "\n".join(lines) + f"\n\033[{self.height + 1};1H"
