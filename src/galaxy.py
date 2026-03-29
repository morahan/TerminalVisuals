import math
import random

from src.base import BaseVisualizer


class GalaxyVisualizer(BaseVisualizer):
    CHARS = {
        "star_bright": "✦",
        "star_dim": "·",
        "star_ascii": "*",
        "star_dim_ascii": ".",
        "dust": " ",
        "bulge": "█",
    }

    def __init__(
        self,
        size: int = 25,
        speed: int = 5,
        brightness: int = 100,
        ascii_mode: bool = False,
        oneshot: bool = False,
        arms: int = 2,
        twinkle: bool = True,
        arm_gap: int = 2,
    ):
        super().__init__(size, speed, brightness, ascii_mode, oneshot)
        self.arms = arms
        self.twinkle = twinkle
        self.arm_gap = arm_gap
        self.stars = self._generate_stars()

    def _get_char(self, name: str) -> str:
        if self.ascii_mode and name in self.CHARS:
            key = f"{name}_ascii"
            return self.CHARS.get(key, self.CHARS[name])
        return self.CHARS.get(name, " ")

    def _generate_stars(self) -> dict:
        stars = {}
        random.seed(42)
        for y in range(self.size):
            for x in range(self.size):
                if random.random() < 0.1:
                    stars[(y, x)] = random.random()
        return stars

    def _color(self, code: str) -> str:
        if self.brightness < 100:
            mapping = {"97": "37", "87": "33", "93": "33", "95": "35"}
            code = mapping.get(code, code)
        return f"\033[{code}m"

    def _in_spiral_arm(self, x: float, y: float, arm_idx: int) -> tuple[bool, float]:
        center = self.size / 2
        dx = x - center
        dy = y - center

        r = math.sqrt(dx * dx + dy * dy)
        if r < 0.5:
            return False, 0

        angle = math.atan2(dy, dx)
        arm_angle = (2 * math.pi * arm_idx / self.arms) + (self.frame * 0.02)

        tightness = 0.3
        target_angle = arm_angle + r * tightness

        angle_diff = abs((angle - target_angle + math.pi) % (2 * math.pi) - math.pi)
        threshold = self.arm_gap * 0.4

        return angle_diff < threshold, r

    def render_frame(self) -> str:
        lines = []
        center = self.size / 2

        for y in range(self.size):
            line = ""
            for x in range(self.size):
                dx = x - center
                dy = y - center
                r = math.sqrt(dx * dx + dy * dy)

                if r < 2:
                    char = self._get_char("bulge")
                    color = self._color("97")
                else:
                    char = self._get_char("star_dim")
                    color = self._color("87")

                    for arm_idx in range(self.arms):
                        in_arm, dist = self._in_spiral_arm(x, y, arm_idx)
                        if in_arm:
                            if dist > 8:
                                char = self._get_char("star_bright")
                                color = self._color("97")
                            else:
                                char = self._get_char("star_dim")
                                color = self._color("93")
                            break

                    if (y, x) in self.stars and r > 3:
                        if self.twinkle:
                            twinkle_factor = math.sin(self.frame * 0.3 + self.stars[(y, x)] * 10)
                            if twinkle_factor > 0:
                                char = self._get_char("star_dim")
                                color = self._color("87")
                        else:
                            char = self._get_char("star_dim")
                            color = self._color("87")

                line += f"{color}{char}{self.ANSI_RESET}" if color != self._color("87") else char

            lines.append(line)

        return "\n".join(lines) + f"\n\033[{int(self.size) + 1};1H"
