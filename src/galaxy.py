from __future__ import annotations

import math
import random

from src.base import BaseVisualizer, Slider, CHAR_ASPECT


class GalaxyVisualizer(BaseVisualizer):
    """Majestic spiral galaxy with glowing core, spiral arms, and dust lanes."""

    CHARS = {
        "core_bright": "\u2600",   # ☀
        "core_glow":   "\u2666",   # ◆
        "arm_bright":  "\u25c6",   # ◆
        "arm_star":    "\u2022",   # •
        "arm_dim":     "\u00b7",   # ·
        "dust":        "\u00b7",   # ·
        "cluster":     "\u2736",   # ✶
        "cluster_ascii": "*",
        "core_bright_ascii": "@",
        "core_glow_ascii": "O",
        "arm_bright_ascii": "*",
        "arm_star_ascii": "o",
        "arm_dim_ascii": ".",
        "dust_ascii": " ",
    }

    sliders = [
        Slider(name="Arms", attr="arms", min_val=2, max_val=6, step=1, fmt="d"),
        Slider(name="Twist", attr="twist", min_val=0.3, max_val=1.5, step=0.1),
        Slider(name="Core", attr="core", min_val=0.2, max_val=1.2, step=0.1),
        Slider(name="Drift", attr="drift", min_val=0.3, max_val=3.0, step=0.25),
        Slider(name="Dust", attr="dust", min_val=0.0, max_val=1.0, step=0.1),
    ]

    def __init__(
        self,
        size: int = 25,
        speed: int = 5,
        brightness: int = 100,
        ascii_mode: bool = False,
        oneshot: bool = False,
        arms: int = 3,
        twist: float = 0.8,
        core: float = 0.7,
        drift: float = 1.5,
        dust: float = 0.5,
    ):
        super().__init__(size, speed, brightness, ascii_mode, oneshot)
        self.arms = arms
        self.twist = twist
        self.core = core
        self.drift = drift
        self.dust = dust
        self._init_stars()

    def _init_stars(self) -> None:
        rng = random.Random(42)
        self.stars = []
        for _ in range(1400):
            angle = rng.random() * math.tau
            dist = rng.random() ** 0.45
            brightness = rng.random()
            self.stars.append({
                "angle": angle,
                "dist": dist,
                "brightness": brightness,
                "twinkle_speed": 0.5 + rng.random() * 2.5,
                "twinkle_phase": rng.random() * math.tau,
                "is_cluster": rng.random() < 0.08,
            })

    def _on_resize(self) -> None:
        self._init_stars()

    def _get_char(self, name: str) -> str:
        if self.ascii_mode:
            key = f"{name}_ascii"
            return self.CHARS.get(key, self.CHARS.get(name, " "))
        return self.CHARS.get(name, " ")

    def _color(self, code: str) -> str:
        if self.brightness < 45:
            subdued = {
                "96;1": "37",
                "96": "37",
                "97": "37",
                "93": "33",
                "33": "2;33",
                "91": "2;31",
                "2;96": "2;37",
                "2;36": "2;37",
                "2;93": "2;33",
            }
            code = subdued.get(code, code.replace(";1", ""))
        elif self.brightness < 75:
            softened = {
                "96;1": "96",
                "97": "37",
                "2;96": "2;36",
                "2;93": "2;33",
            }
            code = softened.get(code, code)
        return f"\033[{code}m"

    def _galaxy_coords(self, star_angle: float, star_dist: float) -> tuple[float, float, float]:
        direction = -1 if self.reversed else 1
        rotation = self.frame * (0.012 + 0.022 * self.drift) * direction
        total_angle = star_angle + rotation

        max_r = min(self.width, self.height / CHAR_ASPECT) * 0.46

        core_fraction = 0.12
        if star_dist < core_fraction:
            t = star_dist / core_fraction
            radius = t * max_r * 0.15
        else:
            t = (star_dist - core_fraction) / (1.0 - core_fraction)
            spiral_turns = t * self.twist * 1.5
            radius = max_r * (0.15 + t * 0.85)
            total_angle += spiral_turns * math.tau

        x = radius * math.cos(total_angle)
        y = radius * math.sin(total_angle) * CHAR_ASPECT
        return x, y, radius

    def _arm_density(self, angle: float, radius: float) -> float:
        if radius < 0.3:
            return 0.0
        max_r = min(self.width, self.height / CHAR_ASPECT) * 0.46
        r_norm = radius / max_r if max_r > 0 else 0
        best = 0.0
        for i in range(self.arms):
            arm_angle = i * math.tau / self.arms
            diff = (angle - arm_angle) % math.tau
            if diff > math.pi:
                diff = math.tau - diff
            base_width = 0.38 + 0.18 * self.twist
            r_factor = max(0.4, 1.0 - r_norm * 0.6)
            arm_width = base_width * r_factor
            density = math.exp(-(diff ** 2) / (arm_width ** 2))
            best = max(best, density)
        return best

    def _dust_attenuation(self, x: float, y: float, time: float) -> float:
        if self.dust < 0.01:
            return 1.0
        dust_phase = time * 0.025
        dust_x = x * 0.5 + math.sin(y * 0.2 + dust_phase) * 4.0
        dust_y = y * 0.4 + math.cos(x * 0.3 + dust_phase * 0.7) * 3.0
        dust_val = (math.sin(dust_x * 0.4 + dust_y * 0.25) *
                    math.cos(dust_x * 0.3 - dust_y * 0.35 + dust_phase))
        dust_val = (dust_val + 1.0) * 0.5
        return 1.0 - self.dust * dust_val * 0.65

    def _core_glow(self, radius: float) -> float:
        if self.core < 0.01:
            return 0.0
        core_r = 2.0 + self.core * 4.5
        if radius >= core_r:
            return 0.0
        return ((core_r - radius) / core_r) ** 1.8 * self.core

    def render_frame(self) -> str:
        cx = self.width / 2.0
        cy = self.height / 2.0
        max_r = min(self.width, self.height / CHAR_ASPECT) * 0.46
        direction = -1 if self.reversed else 1
        current_rotation = self.frame * (0.012 + 0.022 * self.drift) * direction

        cells: dict[tuple[int, int], tuple[float, str, str]] = {}

        for star in self.stars:
            x, y, radius = self._galaxy_coords(star["angle"], star["dist"])

            if radius > max_r or radius < 0.1:
                continue

            sx = cx + x
            sy = cy + y

            if not (0 <= sx < self.width and 0 <= sy < self.height):
                continue

            px = int(sx)
            py = int(sy)

            star_angle_at_time = star["angle"] + current_rotation
            arm_density = self._arm_density(star_angle_at_time, radius)
            dust_atten = self._dust_attenuation(x, y, self.frame)
            core_bright = self._core_glow(radius)

            base_bright = star["brightness"] * (0.15 + arm_density * 0.85) * dust_atten
            effective_brightness = max(base_bright, core_bright * 0.35)

            if effective_brightness < 0.03:
                continue

            twinkle = 0.6 + 0.4 * math.sin(self.frame * star["twinkle_speed"] + star["twinkle_phase"])
            effective_brightness *= twinkle

            key = (py, px)
            existing = cells.get(key)
            if existing is not None and existing[0] > effective_brightness:
                continue

            is_core = radius < 2.8

            if core_bright > 0.5 and is_core:
                char = self._get_char("core_bright")
                color_code = "93;1"
            elif core_bright > 0.25 and is_core:
                char = self._get_char("core_glow")
                color_code = "93"
            elif star["is_cluster"] and arm_density > 0.5 and effective_brightness > 0.4:
                char = self._get_char("cluster")
                color_code = "96;1"
            elif arm_density > 0.6 and effective_brightness > 0.45:
                char = self._get_char("arm_bright")
                color_code = "96" if effective_brightness > 0.3 else "36"
            elif effective_brightness > 0.18:
                char = self._get_char("arm_star")
                color_code = "97" if effective_brightness > 0.35 else "90"
            else:
                char = self._get_char("arm_dim")
                color_code = "2;90"

            color = self._color(color_code)
            cells[key] = (effective_brightness, color, char)

        core_visual_radius = 2.0 + self.core * 4.5
        core_center_intensity = 0.65 + self.core * 0.45
        for dy in range(-5, 6):
            for dx in range(-5, 6):
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > 4.0:
                    continue
                px = int(cx + dx)
                py = int(cy + dy)
                if not (0 <= px < self.width and 0 <= py < self.height):
                    continue

                glow_val = core_center_intensity * (1.0 - dist / 4.5)
                if glow_val < 0.06:
                    continue

                pulse = 0.7 + 0.3 * math.sin(self.frame * 0.12)
                key = (py, px)
                existing = cells.get(key)
                if existing is None or existing[0] < glow_val * pulse:
                    char = (self._get_char("core_bright") if dist < 1.5
                            else self._get_char("core_glow"))
                    cc = "93;1" if dist < 1.5 else "93"
                    cells[key] = (glow_val * pulse, self._color(cc), char)

        lines = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                if (y, x) in cells:
                    _, color, char = cells[(y, x)]
                    row.append(f"{color}{char}{self.ANSI_RESET}")
                else:
                    row.append(" ")
            lines.append("".join(row))

        return "\n".join(lines) + f"\033[{self.height + 1};1H"
