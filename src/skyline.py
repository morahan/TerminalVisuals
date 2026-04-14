from __future__ import annotations

import math

from src.base import BaseVisualizer, Slider


CITY_ORDER = ["newyork", "paris", "london", "tokyo", "sydney", "dubai"]
CITY_LABELS = {
    0: "Auto",
    1: "New York",
    2: "Paris",
    3: "London",
    4: "Tokyo",
    5: "Sydney",
    6: "Dubai",
}


def format_city_choice(value: float) -> str:
    return CITY_LABELS.get(int(value), "Auto")


class SkylineVisualizer(BaseVisualizer):
    """Famous skyline silhouettes that unfold upward one line at a time."""

    CHARS = {
        "solid": "\u2588",         # █
        "solid_ascii": "#",
        "window": "\u00b7",        # ·
        "window_ascii": "o",
        "star": "\u00b7",          # ·
        "star_ascii": ".",
        "spark": "\u2022",         # •
        "spark_ascii": "*",
        "water": "\u223c",         # ∼
        "water_ascii": "~",
        "water_dim": "\u00b7",     # ·
        "water_dim_ascii": "-",
        "vertical": "\u2502",      # │
        "vertical_ascii": "|",
        "horizontal": "\u2500",    # ─
        "horizontal_ascii": "-",
        "diag_up": "\u2571",       # ╱
        "diag_up_ascii": "/",
        "diag_down": "\u2572",     # ╲
        "diag_down_ascii": "\\",
        "dot": "\u25e6",           # ◦
        "dot_ascii": ".",
    }

    sliders = [
        Slider(name="City", attr="city", min_val=0, max_val=6, step=1, fmt="d", display=format_city_choice),
        Slider(name="Glow", attr="glow", min_val=1, max_val=5, step=1, fmt="d"),
    ]

    def __init__(
        self,
        size: int = 0,
        speed: int = 5,
        brightness: int = 100,
        ascii_mode: bool = False,
        oneshot: bool = False,
        city: int = 0,
        glow: int = 3,
    ):
        super().__init__(size, speed, brightness, ascii_mode, oneshot)
        self.city = max(0, min(6, int(city)))
        self.glow = max(1, min(5, int(glow)))
        self._scene_cache: dict[tuple, dict] = {}
        self._tour_anchor = 0.0
        self._pin_anchor = 0.0

    def reset(self) -> None:
        super().reset()
        self._tour_anchor = 0.0
        self._pin_anchor = 0.0

    def adjust_slider(self, slider_idx: int, direction: int) -> None:
        prev_city = self.city
        super().adjust_slider(slider_idx, direction)
        if self.city != prev_city:
            self._tour_anchor = self.frame
            self._pin_anchor = self.frame

    def _get_char(self, name: str) -> str:
        if self.ascii_mode:
            key = f"{name}_ascii"
            return self.CHARS.get(key, self.CHARS.get(name, " "))
        return self.CHARS.get(name, " ")

    @staticmethod
    def _noise(a: float, b: float, c: float = 0.0) -> float:
        value = math.sin(a * 12.9898 + b * 78.233 + c * 37.719) * 43758.5453
        return value - math.floor(value)

    def _paint(self, grid: list[list[tuple[int, str, str] | None]], x: int, y: int, char: str, kind: str, priority: int) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            current = grid[y][x]
            if current is None or priority >= current[0]:
                grid[y][x] = (priority, char, kind)

    def _profile_width(self, profile: list[tuple[float, float]], ratio: float) -> float:
        if ratio <= profile[0][0]:
            return profile[0][1]
        for idx in range(1, len(profile)):
            left_t, left_w = profile[idx - 1]
            right_t, right_w = profile[idx]
            if ratio <= right_t:
                blend = (ratio - left_t) / max(0.001, right_t - left_t)
                return left_w + (right_w - left_w) * blend
        return profile[-1][1]

    def _line_points(self, x1: int, y1: int, x2: int, y2: int) -> list[tuple[int, int]]:
        points: list[tuple[int, int]] = []
        dx = abs(x2 - x1)
        dy = -abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx + dy
        x, y = x1, y1
        while True:
            points.append((x, y))
            if x == x2 and y == y2:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy
        return points

    def _segment_char(self, x1: int, y1: int, x2: int, y2: int) -> str:
        if x1 == x2:
            return self._get_char("vertical")
        if y1 == y2:
            return self._get_char("horizontal")
        if (x2 - x1) * (y2 - y1) < 0:
            return self._get_char("diag_up")
        return self._get_char("diag_down")

    def _draw_line(self, grid: list[list[tuple[int, str, str] | None]], x1: int, y1: int, x2: int, y2: int, kind: str, priority: int) -> None:
        char = self._segment_char(x1, y1, x2, y2)
        for x, y in self._line_points(x1, y1, x2, y2):
            self._paint(grid, x, y, char, kind, priority)

    def _draw_circle(self, grid: list[list[tuple[int, str, str] | None]], cx: int, cy: int, radius: int, kind: str, priority: int) -> None:
        if radius <= 0:
            return
        char = self._get_char("dot")
        steps = max(16, int(radius * 9))
        for idx in range(steps):
            angle = (idx / steps) * math.tau
            x = cx + int(round(math.cos(angle) * radius))
            y = cy + int(round(math.sin(angle) * radius))
            self._paint(grid, x, y, char, kind, priority)

    def _draw_clock(self, grid: list[list[tuple[int, str, str] | None]], cx: int, cy: int, radius: int) -> None:
        self._draw_circle(grid, cx, cy, radius, "warm_accent", 18)
        self._paint(grid, cx, cy, self._get_char("spark"), "warm_accent", 19)
        self._paint(grid, cx, cy - radius, self._get_char("dot"), "warm_accent", 19)
        self._paint(grid, cx + radius, cy, self._get_char("dot"), "warm_accent", 19)

    def _draw_profile_tower(
        self,
        grid: list[list[tuple[int, str, str] | None]],
        center: float,
        base_width: float,
        height_ratio: float,
        horizon: int,
        profile: list[tuple[float, float]],
        seed: int,
        *,
        spire_ratio: float = 0.0,
        crown: str | None = None,
        windows: bool = True,
    ) -> tuple[int, int, int, int]:
        build_height = max(6, horizon - 2)
        height_px = max(4, int(round(height_ratio * build_height)))
        base_px = max(3, int(round(base_width * self.width)))
        cx = int(round(center * (self.width - 1)))
        top = max(1, horizon - height_px + 1)
        spans: list[tuple[int, int, int]] = []
        solid = self._get_char("solid")

        for y in range(top, horizon + 1):
            ratio = (y - top) / max(1, horizon - top)
            width_px = max(1, int(round(base_px * self._profile_width(profile, ratio))))
            left = cx - width_px // 2
            right = left + width_px - 1
            spans.append((y, left, right))
            for x in range(left, right + 1):
                self._paint(grid, x, y, solid, "building", 8)

        if windows:
            for idx, (y, left, right) in enumerate(spans[2:-1], start=2):
                if idx % 2:
                    continue
                if right - left < 4:
                    continue
                step = 2 if right - left < 10 else 3
                for x in range(left + 1, right, step):
                    if self._noise(x + seed * 1.3, y + seed * 0.7, seed) > 0.33:
                        self._paint(grid, x, y, self._get_char("window"), "window", 14)

        if crown == "crown":
            crown_y = top + max(1, height_px // 8)
            self._draw_line(grid, cx - 2, crown_y, cx, top, "accent", 16)
            self._draw_line(grid, cx + 2, crown_y, cx, top, "accent", 16)
            for x in range(cx - 2, cx + 3):
                self._paint(grid, x, crown_y + 1, self._get_char("horizontal"), "accent", 16)
        elif crown == "deck":
            deck_y = top + max(1, height_px // 3)
            for x in range(cx - max(1, base_px // 5), cx + max(1, base_px // 5) + 1):
                self._paint(grid, x, deck_y, self._get_char("horizontal"), "accent", 16)

        if spire_ratio > 0:
            spire_px = max(1, int(round(height_px * spire_ratio)))
            for y in range(top - 1, top - spire_px - 1, -1):
                self._paint(grid, cx, y, self._get_char("vertical"), "accent", 17)

        return cx, top, spans[0][1], spans[-1][2]

    def _draw_eiffel(
        self,
        grid: list[list[tuple[int, str, str] | None]],
        center: float,
        base_width: float,
        height_ratio: float,
        horizon: int,
        *,
        kind: str = "warm_accent",
    ) -> None:
        build_height = max(6, horizon - 2)
        height_px = max(8, int(round(height_ratio * build_height)))
        cx = int(round(center * (self.width - 1)))
        base_px = max(8, int(round(base_width * self.width)))
        top = max(1, horizon - height_px)
        left = cx - base_px // 2
        right = cx + base_px // 2
        lower_left = cx - base_px // 3
        lower_right = cx + base_px // 3

        self._draw_line(grid, left, horizon, cx, top, kind, 18)
        self._draw_line(grid, right, horizon, cx, top, kind, 18)
        self._draw_line(grid, lower_left, horizon, cx, top + height_px // 6, kind, 17)
        self._draw_line(grid, lower_right, horizon, cx, top + height_px // 6, kind, 17)

        for frac in (0.18, 0.38, 0.60, 0.78):
            y = horizon - int(round(height_px * frac))
            span = max(2, int(round(base_px * (1.0 - frac * 0.7) * 0.45)))
            for x in range(cx - span, cx + span + 1):
                self._paint(grid, x, y, self._get_char("horizontal"), kind, 18)

        for x in range(left + 2, right - 1, 2):
            if self._noise(x, top, horizon) > 0.42:
                mid_y = horizon - int(round(height_px * 0.25))
                self._draw_line(grid, x, horizon - 1, cx, mid_y, kind, 16)

        for y in range(top - 2, top + 1):
            self._paint(grid, cx, y, self._get_char("vertical"), kind, 19)

    def _draw_bridge_arc(
        self,
        grid: list[list[tuple[int, str, str] | None]],
        start: float,
        end: float,
        deck_y: int,
        arch_height: int,
    ) -> None:
        x1 = int(round(start * (self.width - 1)))
        x2 = int(round(end * (self.width - 1)))
        prev_x = x1
        prev_y = deck_y
        for x in range(x1, x2 + 1):
            t = (x - x1) / max(1, x2 - x1)
            y = deck_y - int(round(math.sin(t * math.pi) * arch_height))
            self._draw_line(grid, prev_x, prev_y, x, y, "accent", 18)
            prev_x, prev_y = x, y
            if x % 4 == 0:
                self._draw_line(grid, x, y, x, deck_y + 1, "accent", 12)
        for x in range(x1, x2 + 1):
            self._paint(grid, x, deck_y + 1, self._get_char("horizontal"), "building", 10)

    def _draw_shell(
        self,
        grid: list[list[tuple[int, str, str] | None]],
        center: float,
        base_y: int,
        width: float,
        height: float,
        tilt: float,
    ) -> None:
        cx = int(round(center * (self.width - 1)))
        width_px = max(4, int(round(width * self.width)))
        height_px = max(3, int(round(height * max(6, base_y - 2))))
        left = cx - width_px // 2
        right = cx + width_px // 2
        peak_x = cx + int(round(width_px * tilt))
        peak_y = max(1, base_y - height_px)

        self._draw_line(grid, left, base_y, peak_x, peak_y, "warm_accent", 19)
        self._draw_line(grid, peak_x, peak_y, right, base_y - 1, "warm_accent", 19)
        inner_left = cx - max(1, width_px // 4)
        inner_right = cx + max(1, width_px // 6)
        self._draw_line(grid, inner_left, base_y - 1, peak_x, peak_y, "accent", 16)
        self._draw_line(grid, peak_x, peak_y, inner_right, base_y - 2, "accent", 16)
        for x in range(left + 1, right):
            self._paint(grid, x, base_y, self._get_char("horizontal"), "building", 11)

    def _add_stars(self, grid: list[list[tuple[int, str, str] | None]], horizon: int, seed: int) -> None:
        top_band = max(3, horizon - max(4, self.height // 4))
        threshold = 0.992 - self.glow * 0.0015
        for y in range(top_band):
            for x in range(self.width):
                sparkle = self._noise(x + seed * 3.1, y + seed * 1.7, seed * 0.3)
                if sparkle > threshold:
                    char_name = "spark" if sparkle > 0.998 else "star"
                    self._paint(grid, x, y, self._get_char(char_name), "star", 2)

    def _add_water(self, grid: list[list[tuple[int, str, str] | None]], horizon: int) -> None:
        for y in range(horizon + 1, self.height):
            depth = y - horizon
            for x in range(self.width):
                ripple = math.sin(x * 0.34 + depth * 0.9) + 0.45 * math.sin(x * 0.15 - depth * 1.4)
                if ripple > 0.92:
                    char = self._get_char("water")
                elif ripple > 0.25:
                    char = self._get_char("water_dim")
                else:
                    continue
                self._paint(grid, x, y, char, "water", 1)

    def _add_reflection(self, grid: list[list[tuple[int, str, str] | None]], horizon: int) -> None:
        for y in range(horizon + 1, self.height):
            src_y = horizon - 1 - (y - (horizon + 1))
            if src_y < 0:
                break
            offset = int(round(math.sin((y - horizon) * 1.1) * 1.5))
            for x in range(self.width):
                src_x = x - offset
                if not 0 <= src_x < self.width:
                    continue
                cell = grid[src_y][src_x]
                if cell is None:
                    continue
                _, char, kind = cell
                if kind in {"building", "accent", "warm_accent"}:
                    if (x + y) % 2 == 0:
                        refl_kind = "reflection"
                        refl_char = self._get_char("solid") if kind == "building" else char
                        self._paint(grid, x, y, refl_char, refl_kind, 6)
                elif kind == "window" and (x + y) % 3 == 0:
                    self._paint(grid, x, y, self._get_char("window"), "reflection_window", 7)

    def _build_scene(self, scene_name: str) -> dict:
        grid: list[list[tuple[int, str, str] | None]] = [[None] * self.width for _ in range(self.height)]
        water_rows = 0 if self.height < 16 else min(6, max(3, self.height // 5))
        horizon = self.height - water_rows - 2
        if horizon < 8:
            water_rows = 0
            horizon = self.height - 2

        seed = CITY_ORDER.index(scene_name) + 1
        self._add_stars(grid, horizon, seed)
        if water_rows:
            self._add_water(grid, horizon)

        builder = getattr(self, f"_draw_{scene_name}")
        builder(grid, horizon, seed)

        if water_rows:
            self._add_reflection(grid, horizon)

        return {"grid": grid, "horizon": horizon, "seed": seed}

    def _scene(self, scene_name: str) -> dict:
        key = (scene_name, self.width, self.height, self.ascii_mode, self.brightness, self.glow)
        if key not in self._scene_cache:
            self._scene_cache[key] = self._build_scene(scene_name)
        return self._scene_cache[key]

    def _draw_newyork(self, grid: list[list[tuple[int, str, str] | None]], horizon: int, seed: int) -> None:
        self._draw_profile_tower(grid, 0.08, 0.07, 0.22, horizon, [(0.0, 0.9), (1.0, 1.0)], seed + 1)
        self._draw_profile_tower(grid, 0.18, 0.08, 0.34, horizon, [(0.0, 0.72), (1.0, 1.0)], seed + 2)
        self._draw_profile_tower(grid, 0.29, 0.08, 0.48, horizon, [(0.0, 0.45), (0.24, 0.58), (1.0, 1.0)], seed + 3)
        self._draw_profile_tower(grid, 0.40, 0.08, 0.68, horizon, [(0.0, 0.12), (0.12, 0.22), (0.26, 0.36), (0.58, 0.62), (1.0, 1.0)], seed + 4, spire_ratio=0.08, crown="crown")
        self._draw_profile_tower(grid, 0.52, 0.08, 0.74, horizon, [(0.0, 0.18), (0.18, 0.30), (0.40, 0.44), (0.62, 0.62), (1.0, 1.0)], seed + 5, spire_ratio=0.11, crown="deck")
        self._draw_profile_tower(grid, 0.67, 0.10, 0.90, horizon, [(0.0, 0.22), (0.18, 0.30), (0.42, 0.52), (1.0, 1.0)], seed + 6, spire_ratio=0.13)
        self._draw_profile_tower(grid, 0.79, 0.07, 0.56, horizon, [(0.0, 0.32), (0.20, 0.46), (1.0, 1.0)], seed + 7)
        self._draw_profile_tower(grid, 0.89, 0.07, 0.28, horizon, [(0.0, 0.76), (1.0, 1.0)], seed + 8)

    def _draw_paris(self, grid: list[list[tuple[int, str, str] | None]], horizon: int, seed: int) -> None:
        for center, width, height in ((0.10, 0.10, 0.18), (0.24, 0.10, 0.22), (0.39, 0.12, 0.20), (0.72, 0.14, 0.22), (0.88, 0.08, 0.18)):
            self._draw_profile_tower(grid, center, width, height, horizon, [(0.0, 0.92), (1.0, 1.0)], seed + int(center * 10))
        self._draw_eiffel(grid, 0.56, 0.20, 0.86, horizon, kind="warm_accent")
        self._draw_profile_tower(grid, 0.64, 0.09, 0.24, horizon, [(0.0, 0.70), (1.0, 1.0)], seed + 11)

    def _draw_london(self, grid: list[list[tuple[int, str, str] | None]], horizon: int, seed: int) -> None:
        self._draw_profile_tower(grid, 0.12, 0.09, 0.22, horizon, [(0.0, 0.88), (1.0, 1.0)], seed + 1)
        wheel_cx = int(round(0.25 * (self.width - 1)))
        wheel_radius = max(3, min(self.width // 14, max(3, horizon // 5)))
        wheel_cy = horizon - wheel_radius - 1
        self._draw_circle(grid, wheel_cx, wheel_cy, wheel_radius, "accent", 18)
        for spoke in range(0, 8):
            angle = (spoke / 8) * math.tau
            x = wheel_cx + int(round(math.cos(angle) * wheel_radius))
            y = wheel_cy + int(round(math.sin(angle) * wheel_radius))
            self._draw_line(grid, wheel_cx, wheel_cy, x, y, "accent", 14)
        self._draw_line(grid, wheel_cx, wheel_cy + wheel_radius, wheel_cx - 2, horizon + 1, "accent", 14)
        self._draw_line(grid, wheel_cx, wheel_cy + wheel_radius, wheel_cx + 2, horizon + 1, "accent", 14)
        cx, top, _, _ = self._draw_profile_tower(grid, 0.44, 0.05, 0.64, horizon, [(0.0, 0.50), (0.18, 0.72), (1.0, 1.0)], seed + 2, spire_ratio=0.08)
        self._draw_clock(grid, cx, top + max(2, (horizon - top) // 4), 1)
        self._draw_profile_tower(grid, 0.58, 0.06, 0.38, horizon, [(0.0, 0.42), (0.55, 0.82), (1.0, 1.0)], seed + 3)
        self._draw_profile_tower(grid, 0.69, 0.08, 0.86, horizon, [(0.0, 0.10), (0.25, 0.26), (1.0, 1.0)], seed + 4, spire_ratio=0.10)
        self._draw_profile_tower(grid, 0.84, 0.07, 0.28, horizon, [(0.0, 0.86), (1.0, 1.0)], seed + 5)

    def _draw_tokyo(self, grid: list[list[tuple[int, str, str] | None]], horizon: int, seed: int) -> None:
        self._draw_profile_tower(grid, 0.10, 0.08, 0.26, horizon, [(0.0, 0.82), (1.0, 1.0)], seed + 1)
        self._draw_profile_tower(grid, 0.20, 0.08, 0.34, horizon, [(0.0, 0.62), (1.0, 1.0)], seed + 2)
        self._draw_eiffel(grid, 0.34, 0.15, 0.72, horizon, kind="warm_accent")
        self._draw_profile_tower(grid, 0.47, 0.08, 0.42, horizon, [(0.0, 0.70), (1.0, 1.0)], seed + 3)
        cx, top, _, _ = self._draw_profile_tower(grid, 0.69, 0.08, 0.90, horizon, [(0.0, 0.08), (0.12, 0.16), (0.28, 0.20), (0.50, 0.28), (1.0, 1.0)], seed + 4, spire_ratio=0.06, crown="deck")
        for y in (top + 3, top + 6):
            for x in range(cx - 2, cx + 3):
                self._paint(grid, x, y, self._get_char("horizontal"), "accent", 17)
        self._draw_profile_tower(grid, 0.82, 0.08, 0.40, horizon, [(0.0, 0.76), (1.0, 1.0)], seed + 5)
        self._draw_profile_tower(grid, 0.91, 0.06, 0.26, horizon, [(0.0, 0.84), (1.0, 1.0)], seed + 6)

    def _draw_sydney(self, grid: list[list[tuple[int, str, str] | None]], horizon: int, seed: int) -> None:
        self._draw_profile_tower(grid, 0.14, 0.07, 0.32, horizon, [(0.0, 0.64), (1.0, 1.0)], seed + 1)
        self._draw_profile_tower(grid, 0.24, 0.09, 0.46, horizon, [(0.0, 0.44), (1.0, 1.0)], seed + 2)
        self._draw_profile_tower(grid, 0.36, 0.08, 0.28, horizon, [(0.0, 0.82), (1.0, 1.0)], seed + 3)
        self._draw_bridge_arc(grid, 0.16, 0.82, horizon - 3, max(3, horizon // 6))
        shell_base = horizon - 1
        self._draw_shell(grid, 0.56, shell_base, 0.10, 0.22, -0.10)
        self._draw_shell(grid, 0.64, shell_base, 0.11, 0.26, 0.05)
        self._draw_shell(grid, 0.72, shell_base, 0.10, 0.20, 0.10)
        self._draw_shell(grid, 0.78, shell_base, 0.08, 0.15, 0.18)

    def _draw_dubai(self, grid: list[list[tuple[int, str, str] | None]], horizon: int, seed: int) -> None:
        self._draw_profile_tower(grid, 0.14, 0.08, 0.24, horizon, [(0.0, 0.84), (1.0, 1.0)], seed + 1)
        self._draw_profile_tower(grid, 0.28, 0.08, 0.52, horizon, [(0.0, 0.22), (0.24, 0.34), (1.0, 1.0)], seed + 2, spire_ratio=0.06)
        self._draw_profile_tower(grid, 0.40, 0.08, 0.62, horizon, [(0.0, 0.12), (0.24, 0.26), (0.44, 0.38), (1.0, 1.0)], seed + 3, spire_ratio=0.08)
        self._draw_profile_tower(grid, 0.58, 0.10, 0.98, horizon, [(0.0, 0.04), (0.06, 0.08), (0.16, 0.14), (0.28, 0.22), (0.42, 0.34), (0.58, 0.48), (0.78, 0.72), (1.0, 1.0)], seed + 4, spire_ratio=0.15, crown="deck")
        self._draw_profile_tower(grid, 0.72, 0.08, 0.68, horizon, [(0.0, 0.18), (0.20, 0.30), (0.42, 0.42), (1.0, 1.0)], seed + 5, spire_ratio=0.06)
        self._draw_profile_tower(grid, 0.84, 0.08, 0.48, horizon, [(0.0, 0.30), (0.20, 0.44), (1.0, 1.0)], seed + 6)

    def _stage(self) -> tuple[str, str, float]:
        reveal = max(18.0, self.height * 1.3)
        hold = 26.0 + self.glow * 4.0
        fade = 22.0
        rest = 8.0
        cycle = reveal + hold + fade + rest

        if self.city == 0:
            elapsed = self.frame - self._tour_anchor
            index = int(elapsed // cycle) % len(CITY_ORDER)
            city_name = CITY_ORDER[index]
            local_t = elapsed % cycle
        else:
            city_name = CITY_ORDER[max(0, self.city - 1)]
            local_t = (self.frame - self._pin_anchor) % cycle

        if local_t < reveal:
            return city_name, "reveal", local_t / reveal
        if local_t < reveal + hold:
            return city_name, "hold", (local_t - reveal) / hold
        if local_t < reveal + hold + fade:
            return city_name, "fade", (local_t - reveal - hold) / fade
        return city_name, "rest", (local_t - reveal - hold - fade) / rest

    def _kind_color(self, kind: str, boost: float, fade: float, twinkle: float) -> str | None:
        dim = self.brightness < 55
        boost = max(0.0, boost * (1.0 - fade * 0.7))
        twinkle = max(0.0, twinkle * (1.0 - fade * 0.35))

        if kind == "building":
            if boost > 0.82:
                return "\033[97m"
            if boost > 0.40:
                return "\033[96m"
            return "\033[90m" if dim else "\033[2;37m"

        if kind == "accent":
            if boost > 0.68:
                return "\033[97m"
            if boost > 0.28:
                return "\033[36m"
            return "\033[37m" if not dim else "\033[90m"

        if kind == "warm_accent":
            if boost > 0.68:
                return "\033[97m"
            if boost > 0.28 or twinkle > 0.76:
                return "\033[93m"
            return "\033[33m" if not dim else "\033[2;33m"

        if kind == "window":
            if fade > 0.82 and twinkle < 0.86:
                return None
            if boost > 0.48 or twinkle > 0.90:
                return "\033[97m"
            if twinkle > 0.54:
                return "\033[93m"
            return "\033[33m" if not dim else "\033[2;33m"

        if kind == "reflection":
            if boost > 0.50:
                return "\033[36m"
            return "\033[2;34m" if not dim else "\033[90m"

        if kind == "reflection_window":
            if fade > 0.70 and twinkle < 0.92:
                return None
            if twinkle > 0.88 and boost > 0.15:
                return "\033[93m"
            return "\033[2;33m" if not dim else "\033[90m"

        if kind == "water":
            if boost > 0.55:
                return "\033[96m"
            return "\033[2;36m" if not dim else "\033[90m"

        if kind == "star":
            if twinkle > 0.94:
                return "\033[97m"
            if twinkle > 0.72:
                return "\033[96m"
            return "\033[90m" if dim else "\033[2;37m"

        return None

    def render_frame(self) -> str:
        city_name, stage, progress = self._stage()
        scene = self._scene(city_name)
        grid = scene["grid"]
        seed = scene["seed"]
        cutoff = 0
        fade = 0.0
        scan_y: int | None = None

        if stage == "reveal":
            revealed_rows = max(1, int(math.ceil(progress * self.height)))
            cutoff = self.height - revealed_rows
            scan_y = max(0, cutoff)
        elif stage == "fade":
            fade = progress
        elif stage == "rest":
            cutoff = self.height

        lines: list[str] = []
        scan_depth = 2.0 + self.glow * 1.2
        reset = self.ANSI_RESET

        for y, row in enumerate(grid):
            parts: list[str] = []
            prev_color: str | None = None
            row_visible = stage != "reveal" or y >= cutoff
            if stage == "rest":
                row_visible = False
            boost = 0.0
            if scan_y is not None and y >= scan_y:
                boost = max(0.0, 1.0 - ((y - scan_y) / scan_depth))

            for x, cell in enumerate(row):
                char = " "
                color: str | None = None

                if cell is not None:
                    _, base_char, kind = cell
                    twinkle = 0.5 + 0.5 * math.sin(
                        self.frame * (0.08 if kind == "star" else 0.14 + self.glow * 0.02)
                        + x * 0.71
                        + y * 0.23
                        + seed * 1.9
                    )

                    if kind == "star":
                        char = base_char
                        color = self._kind_color(kind, boost, fade * 0.35, twinkle)
                    elif row_visible:
                        char = base_char
                        if kind in {"window", "reflection_window"} and twinkle < 0.10 and fade < 0.7:
                            char = " "
                        color = self._kind_color(kind, boost, fade, twinkle)

                if color != prev_color:
                    if color is None:
                        if prev_color is not None:
                            parts.append(reset)
                    else:
                        parts.append(color)
                    prev_color = color
                parts.append(char)

            if prev_color is not None:
                parts.append(reset)
            lines.append("".join(parts))

        return "\n".join(lines) + f"\n\033[{self.height + 1};1H"
