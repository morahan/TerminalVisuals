import math

from src.base import BaseVisualizer, Slider, CHAR_ASPECT


class SpiralVisualizer(BaseVisualizer):
    """Droid boot-sequence spiral — expands outward from center with glow trail."""

    sliders = [
        Slider(name="Trail", attr="trail", min_val=1, max_val=10, step=1, fmt="d"),
        Slider(name="Growth", attr="growth", min_val=0.1, max_val=0.6, step=0.05, fmt=".2f"),
    ]

    CHARS = {
        "bright": "◆",
        "solid": "█",
        "heavy": "▓",
        "medium": "▒",
        "light": "░",
        "dim": "·",
        "center": "●",
        "bright_ascii": "*",
        "solid_ascii": "#",
        "heavy_ascii": "%",
        "medium_ascii": ":",
        "light_ascii": ".",
        "dim_ascii": ".",
        "center_ascii": "o",
    }

    # (primary, bright, trail) ANSI codes
    PALETTE = [
        ("36", "96", "2;36"),   # cyan
        ("34", "94", "2;34"),   # blue
        ("32", "92", "2;32"),   # green
        ("33", "93", "2;33"),   # yellow
        ("35", "95", "2;35"),   # magenta
        ("31", "91", "2;31"),   # red
    ]

    def __init__(
        self,
        size: int = 25,
        speed: int = 5,
        brightness: int = 100,
        ascii_mode: bool = False,
        oneshot: bool = False,
        arm_gap: int = 2,
        trail: int = 4,
    ):
        super().__init__(size, speed, brightness, ascii_mode, oneshot)
        self.arm_gap = arm_gap
        self.trail = trail
        self.b = 0.25 / max(1, arm_gap)  # spiral tightness
        self.max_radius = min(self.width // 2, int(self.height / CHAR_ASPECT / 2)) - 1
        self.growth = self.max_radius / 80.0  # responsive to terminal size

    def _on_resize(self) -> None:
        old_max_radius = self.max_radius
        self.max_radius = min(self.width // 2, int(self.height / CHAR_ASPECT / 2)) - 1
        if old_max_radius > 0:
            self.growth = self.growth * self.max_radius / old_max_radius

    def _get_char(self, name: str) -> str:
        if self.ascii_mode:
            key = f"{name}_ascii"
            return self.CHARS.get(key, self.CHARS.get(name, " "))
        return self.CHARS.get(name, " ")

    def _color(self, code: str) -> str:
        return f"\033[{code}m"

    def render_frame(self) -> str:
        cx = self.width // 2
        cy = self.height // 2
        grid: list[list[str]] = [[" " for _ in range(self.width)] for _ in range(self.height)]

        # How far the spiral has expanded (grows over time, then resets)
        cycle_length = 200
        t = self.frame % cycle_length
        fade_start = cycle_length - 30

        if t < fade_start:
            max_theta = t * self.growth
        else:
            # Fade phase: stop growing, age everything
            max_theta = fade_start * self.growth

        fade_amount = max(0, t - fade_start) * 0.3

        # Draw the spiral trail
        theta = 0.0
        step = 0.12
        while theta < max_theta:
            r = self.b * theta
            if r > self.max_radius:
                break

            x = r * math.cos(theta)
            y = r * math.sin(theta) * CHAR_ASPECT  # aspect ratio correction

            gx = cx + int(round(x))
            gy = cy + int(round(y))

            if 0 <= gx < self.width and 0 <= gy < self.height:
                age = (max_theta - theta) + fade_amount
                char, color = self._style_point(r, age)
                if char.strip():
                    grid[gy][gx] = f"{color}{char}{self.ANSI_RESET}"

            theta += step

        # Pulsing center dot
        pulse = 0.5 + 0.5 * math.sin(self.frame * 0.2)
        if pulse > 0.3 and t < fade_start + 20:
            center_char = self._get_char("center")
            _, bright, _ = self.PALETTE[0]
            grid[cy][cx] = f"{self._color(bright)}\033[1m{center_char}{self.ANSI_RESET}"

        # Build output
        lines = []
        for row in grid:
            lines.append("".join(row))
        return "\n".join(lines) + f"\n\033[{self.height + 1};1H"

    def _style_point(self, radius: float, age: float) -> tuple[str, str]:
        ring_idx = int(radius / max(1, self.arm_gap))
        primary, bright, trail = self.PALETTE[ring_idx % len(self.PALETTE)]

        dim = self.brightness < 50

        if age < 0.5:
            char = self._get_char("bright")
            color = self._color(f"{bright};1") if not dim else self._color(bright)
        elif age < self.trail * 0.3:
            char = self._get_char("solid")
            color = self._color(bright)
        elif age < self.trail * 0.6:
            char = self._get_char("heavy")
            color = self._color(primary)
        elif age < self.trail:
            char = self._get_char("medium")
            color = self._color(primary)
        elif age < self.trail + 2:
            char = self._get_char("light")
            color = self._color(trail)
        elif age < self.trail + 4:
            char = self._get_char("dim")
            color = self._color(trail)
        else:
            char = " "
            color = ""

        if dim and color:
            color = f"\033[2m{color}"

        return char, color
