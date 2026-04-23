from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable
from zoneinfo import ZoneInfo

from src.base import BaseVisualizer, Slider


PHASE_TIMINGS = {
    "city_display": 10.0,
    "transition": 30.0,
}


@dataclass(frozen=True)
class CityStyle:
    primary: str
    secondary: str
    accent_rate: float
    twinkle_rate: float
    fog: bool = False
    petals: bool = False
    beams: bool = False
    shells: bool = False
    bloom: str = "\033[97m"


CITY_STYLES = {
    "newyork": CityStyle("\033[96m", "\033[97m", 1.25, 1.35, bloom="\033[96m"),
    "paris": CityStyle("\033[93m", "\033[33m", 0.82, 0.90, bloom="\033[93m"),
    "london": CityStyle("\033[36m", "\033[94m", 0.75, 0.85, fog=True, bloom="\033[36m"),
    "tokyo": CityStyle("\033[96m", "\033[95m", 1.18, 1.20, petals=True, bloom="\033[95m"),
    "sydney": CityStyle("\033[97m", "\033[93m", 0.88, 0.92, shells=True, bloom="\033[97m"),
    "dubai": CityStyle("\033[93m", "\033[33m", 0.95, 0.82, beams=True, bloom="\033[93m"),
}

LAYER_BIAS = {
    "star": 0.06,
    "water": 0.12,
    "reflection": 0.20,
    "reflection_window": 0.28,
    "fog": 0.34,
    "window": 0.50,
    "building": 0.68,
    "accent": 0.82,
    "warm_accent": 0.88,
    "beam": 0.90,
}

LONDON_ZONE = ZoneInfo("Europe/London")


def city_scene(label: str | None = None) -> Callable[[Callable], Callable]:
    def decorate(func: Callable) -> Callable:
        setattr(func, "_skyline_scene", True)
        setattr(func, "_skyline_label", label)
        return func

    return decorate


class SkylineVisualizer(BaseVisualizer):
    """Famous skyline silhouettes with a cinematic shuffled auto-tour."""

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
        "shade_light": "\u2591",   # ░
        "shade_light_ascii": ".",
        "shade_mid": "\u2592",     # ▒
        "shade_mid_ascii": ":",
        "shade_heavy": "\u2593",   # ▓
        "shade_heavy_ascii": "#",
        "petal": "\u2022",         # •
        "petal_ascii": "*",
    }

    sliders: list[Slider] = []

    def __init__(
        self,
        size: int = 0,
        speed: int = 5,
        brightness: int = 100,
        ascii_mode: bool = False,
        oneshot: bool = False,
        city: int = 0,
        glow: int = 3,
        *,
        time_source: Callable[[], float] | None = None,
        london_time_source: Callable[[], datetime] | None = None,
        rng: random.Random | None = None,
    ):
        super().__init__(size, speed, brightness, ascii_mode, oneshot)
        self.city = max(0, min(6, int(city)))
        self.glow = max(1, min(5, int(glow)))
        self._time_source = time_source or time.monotonic
        self._london_time_source = london_time_source
        self._rng = rng or random.Random()
        self._city_order, self._city_labels = self._discover_city_scenes()
        self._scene_cache: dict[tuple, dict] = {}
        self._auto_bag: list[str] = []
        self._current_city: str | None = None
        self._next_city: str | None = None
        self._phase = "city_display"
        self._phase_started_at = 0.0
        self._transition_data: dict | None = None
        self._initialized = False
        self.sliders = [
            Slider(
                name="City",
                attr="city",
                min_val=0,
                max_val=max(0, len(self._city_order)),
                step=1,
                fmt="d",
                display=self._format_city_choice,
            ),
            Slider(name="Glow", attr="glow", min_val=1, max_val=5, step=1, fmt="d"),
        ]
        self.city = max(0, min(len(self._city_order), self.city))

    def reset(self) -> None:
        super().reset()
        self._auto_bag = []
        self._current_city = None
        self._next_city = None
        self._phase = "city_display"
        self._phase_started_at = self._time_source()
        self._transition_data = None
        self._initialized = False

    def _on_resize(self) -> None:
        self._scene_cache.clear()
        self._transition_data = None

    def adjust_slider(self, slider_idx: int, direction: int) -> None:
        prev_city = self.city
        prev_glow = self.glow
        super().adjust_slider(slider_idx, direction)
        if self.city != prev_city:
            self.reset()
        elif self.glow != prev_glow:
            self._scene_cache.clear()
            self._transition_data = None

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

    def _paint_float(self, grid: list[list[tuple[int, str, str] | None]], x: float, y: float, char: str, kind: str, priority: int) -> None:
        self._paint(grid, int(round(x)), int(round(y)), char, kind, priority)

    def _copy_grid(self, grid: list[list[tuple[int, str, str] | None]]) -> list[list[tuple[int, str, str] | None]]:
        return [row[:] for row in grid]

    def _motion_time(self, now: float) -> float:
        return now * (0.45 + self.speed * 0.18)

    def _london_now(self) -> datetime:
        if self._london_time_source is not None:
            return self._london_time_source()
        return datetime.now(LONDON_ZONE)

    @classmethod
    def _discover_city_scenes(cls) -> tuple[list[str], dict[int, str]]:
        order: list[str] = []
        labels: dict[int, str] = {0: "Auto"}
        seen: set[str] = set()
        for base in reversed(cls.mro()):
            for name, attr in getattr(base, "__dict__", {}).items():
                if not callable(attr) or not getattr(attr, "_skyline_scene", False):
                    continue
                city_name = name.removeprefix("_draw_")
                if city_name in seen:
                    continue
                seen.add(city_name)
                order.append(city_name)
        preferred = ["newyork", "paris", "london", "tokyo", "sydney", "dubai"]
        extras = sorted(name for name in order if name not in preferred)
        rank = {name: idx for idx, name in enumerate(preferred + extras)}
        order.sort(key=lambda name: rank.get(name, len(rank)))
        for idx, city_name in enumerate(order, start=1):
            func = getattr(cls, f"_draw_{city_name}")
            label = getattr(func, "_skyline_label", None) or city_name.replace("_", " ").title()
            labels[idx] = label
        return order, labels

    @classmethod
    def city_choices(cls) -> list[str]:
        order, _ = cls._discover_city_scenes()
        return ["auto", *order]

    @classmethod
    def city_choice_map(cls) -> dict[str, int]:
        order, _ = cls._discover_city_scenes()
        return {"auto": 0, **{name: idx for idx, name in enumerate(order, start=1)}}

    def _format_city_choice(self, value: float) -> str:
        return self._city_labels.get(int(value), "Auto")

    def _city_style(self, city_name: str) -> CityStyle:
        return CITY_STYLES.get(city_name, CityStyle("\033[96m", "\033[37m", 1.0, 1.0, bloom="\033[97m"))

    def _city_seed(self, city_name: str) -> int:
        if city_name in self._city_order:
            return self._city_order.index(city_name) + 1
        return max(1, int(self._noise(len(city_name), len(city_name) * 0.7) * 997))

    def _city_from_slider(self) -> str:
        if not self._city_order:
            return "skyline"
        return self._city_order[max(0, min(len(self._city_order) - 1, self.city - 1))]

    def _ensure_initialized(self, now: float) -> None:
        if self._initialized:
            return
        self._phase_started_at = now
        if self.city == 0:
            self._current_city = self._take_next_auto_city()
        else:
            self._current_city = self._city_from_slider()
        self._initialized = True

    def _refill_bag(self) -> None:
        self._auto_bag = self._city_order[:]
        self._rng.shuffle(self._auto_bag)

    def _take_next_auto_city(self) -> str:
        if not self._auto_bag:
            self._refill_bag()
        return self._auto_bag.pop()

    def _start_transition(self, now: float) -> None:
        if self._current_city is None:
            return
        self._next_city = self._take_next_auto_city()
        self._transition_data = self._build_transition_scene(self._current_city, self._next_city)
        self._phase = "transition"
        self._phase_started_at = now

    def _advance_phase(self, now: float) -> None:
        if self.city != 0:
            self._current_city = self._city_from_slider()
            self._next_city = None
            self._transition_data = None
            self._phase = "city_display"
            self._phase_started_at = now
            return

        while True:
            elapsed = now - self._phase_started_at
            duration = PHASE_TIMINGS[self._phase]
            if elapsed < duration:
                break

            self._phase_started_at += duration
            if self._phase == "city_display":
                self._start_transition(self._phase_started_at)
                continue
            if self._phase == "transition":
                self._current_city = self._next_city
                self._next_city = None
                self._transition_data = None
                self._phase = "city_display"
                continue

    def _stage(self, now: float | None = None) -> tuple[str, str | None, str, float]:
        now = self._time_source() if now is None else now
        self._ensure_initialized(now)
        self._advance_phase(now)
        duration = PHASE_TIMINGS[self._phase]
        progress = min(1.0, max(0.0, (now - self._phase_started_at) / max(0.001, duration)))
        fallback_city = self._city_order[0] if self._city_order else "skyline"
        return self._current_city or fallback_city, self._next_city, self._phase, progress

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

    def _clock_hand_points(self, cx: int, cy: int, radius: int, now_dt: datetime | None = None) -> list[tuple[int, int]]:
        now_dt = self._london_now() if now_dt is None else now_dt
        minute_angle = (now_dt.minute / 60.0) * math.tau - math.pi / 2
        hour_angle = (((now_dt.hour % 12) + now_dt.minute / 60.0) / 12.0) * math.tau - math.pi / 2
        hour_len = max(1, radius - 1)
        minute_len = max(1, radius)
        return [
            (
                cx + int(round(math.cos(hour_angle) * hour_len)),
                cy + int(round(math.sin(hour_angle) * hour_len)),
            ),
            (
                cx + int(round(math.cos(minute_angle) * minute_len)),
                cy + int(round(math.sin(minute_angle) * minute_len)),
            ),
        ]

    def _draw_clock(self, grid: list[list[tuple[int, str, str] | None]], cx: int, cy: int, radius: int) -> None:
        self._draw_circle(grid, cx, cy, radius, "warm_accent", 18)
        self._paint(grid, cx, cy, self._get_char("spark"), "warm_accent", 19)
        self._paint(grid, cx, cy - radius, self._get_char("dot"), "warm_accent", 19)
        self._paint(grid, cx + radius, cy, self._get_char("dot"), "warm_accent", 19)
        self._paint(grid, cx, cy + radius, self._get_char("dot"), "warm_accent", 19)
        self._paint(grid, cx - radius, cy, self._get_char("dot"), "warm_accent", 19)

    def _draw_arc_de_triomphe(self, grid: list[list[tuple[int, str, str] | None]], center: float, base_y: int, width: float) -> None:
        cx = int(round(center * (self.width - 1)))
        half = max(3, int(round(width * self.width / 2)))
        top = max(1, base_y - 3)
        for x in range(cx - half, cx + half + 1):
            self._paint(grid, x, base_y, self._get_char("horizontal"), "building", 10)
            self._paint(grid, x, top, self._get_char("horizontal"), "accent", 14)
        for y in range(top, base_y + 1):
            self._paint(grid, cx - half, y, self._get_char("vertical"), "building", 10)
            self._paint(grid, cx + half, y, self._get_char("vertical"), "building", 10)
        for y in range(top + 1, base_y):
            self._paint(grid, cx - 1, y, self._get_char("vertical"), "accent", 12)
            self._paint(grid, cx + 1, y, self._get_char("vertical"), "accent", 12)

    def _draw_pagoda(
        self,
        grid: list[list[tuple[int, str, str] | None]],
        center: float,
        horizon: int,
        height_ratio: float,
    ) -> None:
        cx = int(round(center * (self.width - 1)))
        height_px = max(6, int(round(height_ratio * max(8, horizon - 2))))
        top = max(1, horizon - height_px)
        for idx, span in enumerate((6, 5, 4, 3)):
            y = horizon - idx * max(1, height_px // 4)
            for x in range(cx - span, cx + span + 1):
                self._paint(grid, x, y, self._get_char("horizontal"), "warm_accent", 18)
            if idx < 3:
                self._draw_line(grid, cx - max(1, span - 1), y, cx, y - 2, "accent", 15)
                self._draw_line(grid, cx + max(1, span - 1), y, cx, y - 2, "accent", 15)
        for y in range(top, horizon + 1):
            self._paint(grid, cx, y, self._get_char("vertical"), "accent", 16)

    def _draw_geometric_crown(self, grid: list[list[tuple[int, str, str] | None]], cx: int, top: int, width: int) -> None:
        half = max(2, width // 2)
        self._draw_line(grid, cx - half, top + 1, cx, top - 1, "warm_accent", 18)
        self._draw_line(grid, cx + half, top + 1, cx, top - 1, "warm_accent", 18)
        self._draw_line(grid, cx - max(1, half - 1), top + 2, cx + max(1, half - 1), top + 2, "accent", 17)

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
                    if self._noise(x + seed * 1.3, y + seed * 0.7, seed) > 0.28:
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
    ) -> tuple[int, int]:
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
        return cx, top

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
    ) -> tuple[int, int]:
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
        return peak_x, peak_y

    def _add_stars(self, grid: list[list[tuple[int, str, str] | None]], horizon: int, seed: int) -> None:
        top_band = max(3, horizon - max(4, self.height // 4))
        threshold = 0.992 - self.glow * 0.0019
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

    def _collect_layers(self, grid: list[list[tuple[int, str, str] | None]]) -> dict[str, list[tuple[int, int, int, str]]]:
        layers: dict[str, list[tuple[int, int, int, str]]] = {}
        for y, row in enumerate(grid):
            for x, cell in enumerate(row):
                if cell is None:
                    continue
                priority, char, kind = cell
                layers.setdefault(kind, []).append((x, y, priority, char))
        return layers

    def _build_scene(self, scene_name: str) -> dict:
        grid: list[list[tuple[int, str, str] | None]] = [[None] * self.width for _ in range(self.height)]
        water_rows = 0 if self.height < 16 else min(6, max(3, self.height // 5))
        horizon = self.height - water_rows - 2
        if horizon < 8:
            water_rows = 0
            horizon = self.height - 2

        seed = self._city_seed(scene_name)
        self._add_stars(grid, horizon, seed)
        if water_rows:
            self._add_water(grid, horizon)

        builder = getattr(self, f"_draw_{scene_name}")
        builder(grid, horizon, seed)

        if water_rows:
            self._add_reflection(grid, horizon)

        return {
            "grid": grid,
            "horizon": horizon,
            "seed": seed,
            "layers": self._collect_layers(grid),
        }

    def _scene(self, scene_name: str) -> dict:
        key = (scene_name, self.width, self.height, self.ascii_mode, self.brightness, self.glow)
        if key not in self._scene_cache:
            self._scene_cache[key] = self._build_scene(scene_name)
        return self._scene_cache[key]

    @city_scene("New York")
    def _draw_newyork(self, grid: list[list[tuple[int, str, str] | None]], horizon: int, seed: int) -> None:
        self._draw_profile_tower(grid, 0.08, 0.07, 0.22, horizon, [(0.0, 0.9), (1.0, 1.0)], seed + 1)
        self._draw_profile_tower(grid, 0.18, 0.08, 0.34, horizon, [(0.0, 0.72), (1.0, 1.0)], seed + 2)
        self._draw_profile_tower(grid, 0.29, 0.08, 0.48, horizon, [(0.0, 0.45), (0.24, 0.58), (1.0, 1.0)], seed + 3)
        self._draw_profile_tower(grid, 0.40, 0.08, 0.68, horizon, [(0.0, 0.12), (0.12, 0.22), (0.26, 0.36), (0.58, 0.62), (1.0, 1.0)], seed + 4, spire_ratio=0.08, crown="crown")
        self._draw_profile_tower(grid, 0.52, 0.08, 0.74, horizon, [(0.0, 0.18), (0.18, 0.30), (0.40, 0.44), (0.62, 0.62), (1.0, 1.0)], seed + 5, spire_ratio=0.11, crown="deck")
        cx, top, _, _ = self._draw_profile_tower(grid, 0.67, 0.10, 0.90, horizon, [(0.0, 0.22), (0.18, 0.30), (0.42, 0.52), (1.0, 1.0)], seed + 6, spire_ratio=0.13)
        self._draw_geometric_crown(grid, cx, top + 1, 6)
        self._draw_profile_tower(grid, 0.79, 0.07, 0.56, horizon, [(0.0, 0.32), (0.20, 0.46), (1.0, 1.0)], seed + 7)
        self._draw_profile_tower(grid, 0.89, 0.07, 0.28, horizon, [(0.0, 0.76), (1.0, 1.0)], seed + 8)

    @city_scene("Paris")
    def _draw_paris(self, grid: list[list[tuple[int, str, str] | None]], horizon: int, seed: int) -> None:
        for center, width, height in ((0.10, 0.10, 0.18), (0.24, 0.10, 0.22), (0.39, 0.12, 0.20), (0.72, 0.14, 0.22), (0.88, 0.08, 0.18)):
            self._draw_profile_tower(grid, center, width, height, horizon, [(0.0, 0.92), (1.0, 1.0)], seed + int(center * 10))
        self._draw_arc_de_triomphe(grid, 0.22, horizon, 0.10)
        self._draw_eiffel(grid, 0.56, 0.20, 0.86, horizon, kind="warm_accent")
        self._draw_profile_tower(grid, 0.64, 0.09, 0.24, horizon, [(0.0, 0.70), (1.0, 1.0)], seed + 11)

    @city_scene("London")
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

    @city_scene("Tokyo")
    def _draw_tokyo(self, grid: list[list[tuple[int, str, str] | None]], horizon: int, seed: int) -> None:
        self._draw_profile_tower(grid, 0.10, 0.08, 0.26, horizon, [(0.0, 0.82), (1.0, 1.0)], seed + 1)
        self._draw_profile_tower(grid, 0.20, 0.08, 0.34, horizon, [(0.0, 0.62), (1.0, 1.0)], seed + 2)
        self._draw_pagoda(grid, 0.34, horizon, 0.46)
        self._draw_profile_tower(grid, 0.47, 0.08, 0.42, horizon, [(0.0, 0.70), (1.0, 1.0)], seed + 3)
        cx, top, _, _ = self._draw_profile_tower(grid, 0.69, 0.08, 0.90, horizon, [(0.0, 0.08), (0.12, 0.16), (0.28, 0.20), (0.50, 0.28), (1.0, 1.0)], seed + 4, spire_ratio=0.06, crown="deck")
        for y in (top + 3, top + 6):
            for x in range(cx - 2, cx + 3):
                self._paint(grid, x, y, self._get_char("horizontal"), "accent", 17)
        self._draw_profile_tower(grid, 0.82, 0.08, 0.40, horizon, [(0.0, 0.76), (1.0, 1.0)], seed + 5)
        self._draw_profile_tower(grid, 0.91, 0.06, 0.26, horizon, [(0.0, 0.84), (1.0, 1.0)], seed + 6)

    @city_scene("Sydney")
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

    @city_scene("Dubai")
    def _draw_dubai(self, grid: list[list[tuple[int, str, str] | None]], horizon: int, seed: int) -> None:
        self._draw_profile_tower(grid, 0.14, 0.08, 0.24, horizon, [(0.0, 0.84), (1.0, 1.0)], seed + 1)
        self._draw_profile_tower(grid, 0.28, 0.08, 0.52, horizon, [(0.0, 0.22), (0.24, 0.34), (1.0, 1.0)], seed + 2, spire_ratio=0.06)
        self._draw_profile_tower(grid, 0.40, 0.08, 0.62, horizon, [(0.0, 0.12), (0.24, 0.26), (0.44, 0.38), (1.0, 1.0)], seed + 3, spire_ratio=0.08)
        cx, top, _, _ = self._draw_profile_tower(grid, 0.58, 0.10, 0.98, horizon, [(0.0, 0.04), (0.06, 0.08), (0.16, 0.14), (0.28, 0.22), (0.42, 0.34), (0.58, 0.48), (0.78, 0.72), (1.0, 1.0)], seed + 4, spire_ratio=0.15, crown="deck")
        self._draw_geometric_crown(grid, cx, top + 1, 8)
        self._draw_profile_tower(grid, 0.72, 0.08, 0.68, horizon, [(0.0, 0.18), (0.20, 0.30), (0.42, 0.42), (1.0, 1.0)], seed + 5, spire_ratio=0.06)
        self._draw_profile_tower(grid, 0.84, 0.08, 0.48, horizon, [(0.0, 0.30), (0.20, 0.44), (1.0, 1.0)], seed + 6)

    def _build_transition_scene(self, city_from: str, city_to: str) -> dict:
        from_scene = self._scene(city_from)
        to_scene = self._scene(city_to)
        center_x = (self.width - 1) / 2.0
        center_y = (self.height - 1) / 2.0
        pair_seed = self._city_seed(city_from) * 11 + self._city_seed(city_to) * 17
        angle = self._noise(pair_seed * 0.07, pair_seed * 0.13, pair_seed * 0.19) * math.tau
        ux = math.cos(angle)
        uy = math.sin(angle)
        vx = -uy
        vy = ux
        corners = [
            (0.0, 0.0),
            (0.0, self.height - 1.0),
            (self.width - 1.0, 0.0),
            (self.width - 1.0, self.height - 1.0),
        ]
        projections = [x * ux + y * uy for x, y in corners]
        min_proj = min(projections)
        max_proj = max(projections)
        thresholds: list[list[float]] = [[0.0] * self.width for _ in range(self.height)]

        for y in range(self.height):
            for x in range(self.width):
                along = (x * ux + y * uy - min_proj) / max(0.001, max_proj - min_proj)
                across = ((x - center_x) * vx + (y - center_y) * vy) / max(1.0, min(self.width, self.height))
                bend = 0.05 * math.sin(across * 6.0 + pair_seed * 0.09)
                bend += 0.03 * math.sin(along * math.pi * 2.0 + pair_seed * 0.05)
                thresholds[y][x] = min(0.97, max(0.03, along + bend))

        return {
            "from_scene": from_scene,
            "to_scene": to_scene,
            "center": (center_x, center_y),
            "pair_seed": pair_seed,
            "thresholds": thresholds,
            "seam_width": 0.02 + self.glow * 0.006,
        }

    def _ease_out(self, value: float) -> float:
        value = min(1.0, max(0.0, value))
        return 1.0 - (1.0 - value) ** 3

    def _ease_in_out(self, value: float) -> float:
        value = min(1.0, max(0.0, value))
        return 0.5 - 0.5 * math.cos(value * math.pi)

    def _apply_london_fog(
        self,
        canvas: list[list[tuple[int, str, str] | None]],
        scene: dict,
        motion_t: float,
    ) -> None:
        horizon = scene["horizon"]
        fog_top = max(0, horizon - 3)
        fog_bottom = min(self.height - 1, horizon)
        fog_threshold = 0.42 - self.glow * 0.015

        for y in range(fog_top, fog_bottom + 1):
            depth = (y - fog_top) / max(1, fog_bottom - fog_top + 1)
            for x in range(self.width):
                cell = canvas[y][x]
                if cell is not None and cell[2] in {"water", "reflection", "reflection_window"}:
                    continue
                band = 0.50 + 0.24 * math.sin(x * 0.12 + motion_t * 0.24 + y * 0.45)
                band += 0.18 * math.sin(x * 0.04 - motion_t * 0.11 + y * 0.18)
                band -= depth * 0.06
                if band > fog_threshold:
                    self._paint(canvas, x, y, self._get_char("shade_light"), "fog", 4)

    def _ambient_overlay(self, canvas: list[list[tuple[int, str, str] | None]], city_name: str, scene: dict, motion_t: float, emphasis: float) -> None:
        horizon = scene["horizon"]
        glow_amp = 0.6 + self.glow * 0.28

        if city_name == "newyork":
            for x_ratio, y_ratio in ((0.40, 0.24), (0.52, 0.18), (0.67, 0.12)):
                x = int(round(x_ratio * (self.width - 1)))
                y = max(1, int(round(y_ratio * horizon)))
                pulse = 0.5 + 0.5 * math.sin(motion_t * 1.6 + x * 0.2)
                if pulse > 0.35:
                    self._paint(canvas, x, y, self._get_char("spark"), "accent", 22)
                    if pulse > 0.72 and y + 1 < self.height:
                        self._paint(canvas, x, y + 1, self._get_char("vertical"), "accent", 19)

        elif city_name == "paris":
            cx = int(round(0.56 * (self.width - 1)))
            top = max(2, horizon - int(round(0.86 * max(6, horizon - 2))))
            radius = 1 + min(5, self.glow)
            halo = 0.5 + 0.5 * math.sin(motion_t * 0.8)
            for idx in range(radius * 10):
                angle = (idx / max(1, radius * 10)) * math.tau
                hx = cx + int(round(math.cos(angle) * (radius + halo * glow_amp)))
                hy = top + 2 + int(round(math.sin(angle) * (radius * 0.55)))
                self._paint(canvas, hx, hy, self._get_char("dot"), "warm_accent", 18)

        elif city_name == "london":
            cx = int(round(0.44 * (self.width - 1)))
            top = max(1, horizon - int(round(0.64 * max(6, horizon - 2))) + 1)
            cy = top + max(2, (horizon - top) // 4)
            for hand_x, hand_y in self._clock_hand_points(cx, cy, 1):
                self._draw_line(canvas, cx, cy, hand_x, hand_y, "warm_accent", 20)
            self._apply_london_fog(canvas, scene, motion_t)

        elif city_name == "tokyo":
            petals = 5 + self.glow * 2
            for idx in range(petals):
                px = int((self.width * (0.25 + 0.11 * idx) + math.sin(motion_t * 0.8 + idx) * 5.0) % max(1, self.width))
                py = max(0, int((motion_t * 0.7 + idx * 1.7) % max(3, horizon)))
                self._paint(canvas, px, py, self._get_char("petal"), "petal", 5)

        elif city_name == "sydney":
            shell_positions = (0.56, 0.64, 0.72, 0.78)
            for idx, x_ratio in enumerate(shell_positions):
                x = int(round(x_ratio * (self.width - 1)))
                y = max(1, horizon - 6 + idx)
                pulse = 0.5 + 0.5 * math.sin(motion_t * 0.9 + idx * 0.7)
                if pulse > 0.26:
                    self._paint(canvas, x, y, self._get_char("spark"), "warm_accent", 20)
            for x in range(self.width):
                water = math.sin(x * 0.22 + motion_t * 0.9)
                if water > 0.92 and horizon + 2 < self.height:
                    self._paint(canvas, x, horizon + 2, self._get_char("spark"), "reflection_window", 9)

        elif city_name == "dubai":
            for x_ratio in (0.28, 0.40, 0.58, 0.72):
                x = int(round(x_ratio * (self.width - 1)))
                beam_top = max(1, horizon - int(round((0.35 + x_ratio * 0.4) * max(6, horizon - 2))))
                travel = int((motion_t * (1.0 + x_ratio)) % max(1, horizon - beam_top + 1))
                for step in range(2 + self.glow):
                    y = beam_top + travel - step
                    if 0 <= y < self.height:
                        self._paint(canvas, x, y, self._get_char("vertical"), "beam", 21)

        if emphasis > 0.0:
            center_x = (self.width - 1) / 2.0
            center_y = horizon / 2.0
            spread = 2.0 + emphasis * (2.0 + self.glow * 0.6)
            for idx in range(self.width):
                lift = math.sin(idx * 0.18 + motion_t * 0.6) * spread
                x = idx
                y = int(round(center_y + lift))
                if 0 <= y < horizon:
                    self._paint(canvas, x, y, self._get_char("shade_light"), "glow", 3)

    def _compose_city_canvas(self, city_name: str, scene: dict, now: float, stage: str, progress: float) -> list[list[tuple[int, str, str] | None]]:
        canvas = self._copy_grid(scene["grid"])
        if stage == "transition":
            return canvas
        motion_t = self._motion_time(now) * self._city_style(city_name).accent_rate
        emphasis = 0.0
        if stage == "city_display":
            emphasis = 0.18 + 0.12 * math.sin(motion_t * 0.3)
        self._ambient_overlay(canvas, city_name, scene, motion_t, emphasis)
        return canvas

    def _kind_color(self, city_name: str, kind: str, boost: float, fade: float, twinkle: float) -> str | None:
        style = self._city_style(city_name)
        dim = self.brightness < 55
        boost = max(0.0, boost * (1.0 - fade * 0.55))
        twinkle = max(0.0, twinkle * (1.0 - fade * 0.28))

        if kind == "building":
            if boost > 0.88:
                return "\033[97m"
            if boost > 0.50:
                return style.primary
            return "\033[90m" if dim else "\033[2;37m"

        if kind == "accent":
            if boost > 0.74:
                return "\033[97m"
            if boost > 0.24 or twinkle > 0.72:
                return style.primary
            return style.secondary if not dim else "\033[90m"

        if kind == "warm_accent":
            if boost > 0.74:
                return "\033[97m"
            if boost > 0.24 or twinkle > 0.66:
                return style.secondary
            return style.primary if not dim else "\033[2;37m"

        if kind == "window":
            if fade > 0.86 and twinkle < 0.86:
                return None
            if boost > 0.58 or twinkle > 0.92:
                return "\033[97m"
            if city_name == "newyork" and twinkle > 0.34:
                return style.secondary
            if city_name == "tokyo" and twinkle > 0.48:
                return style.primary
            return "\033[33m" if not dim else "\033[2;33m"

        if kind == "reflection":
            if boost > 0.56:
                return style.primary
            return "\033[2;34m" if not dim else "\033[90m"

        if kind == "reflection_window":
            if fade > 0.74 and twinkle < 0.92:
                return None
            if twinkle > 0.86:
                return style.secondary
            return "\033[2;33m" if not dim else "\033[90m"

        if kind == "water":
            if boost > 0.60:
                return style.primary
            return "\033[2;36m" if not dim else "\033[90m"

        if kind == "star":
            if twinkle > 0.94:
                return "\033[97m"
            if twinkle > 0.72:
                return style.primary
            return "\033[90m" if dim else "\033[2;37m"

        if kind in {"glow", "seed", "thread", "beam"}:
            if boost > 0.48 or twinkle > 0.66:
                return "\033[97m"
            return style.primary

        if kind in {"bloom", "petal"}:
            if boost > 0.46 or twinkle > 0.52:
                return "\033[97m"
            return style.secondary

        if kind == "fog":
            return "\033[2;37m" if not dim else "\033[90m"

        return None

    def _render_canvas(
        self,
        city_name: str,
        canvas: list[list[tuple[int, str, str] | None]],
        now: float,
        *,
        phase: str,
        progress: float,
        fade: float = 0.0,
        phase_boost: float = 0.0,
    ) -> str:
        scene_seed = self._city_seed(city_name)
        style = self._city_style(city_name)
        lines: list[str] = []
        reset = self.ANSI_RESET
        motion_t = self._motion_time(now)

        for y, row in enumerate(canvas):
            parts: list[str] = []
            prev_color: str | None = None
            row_breath = phase_boost * (0.6 + 0.4 * math.sin(motion_t * 0.25 + y * 0.23))
            for x, cell in enumerate(row):
                display_x = self.width - 1 - x if self.reversed else x
                char = " "
                color: str | None = None
                cell = canvas[y][display_x] if 0 <= display_x < self.width else None
                if cell is not None:
                    _, base_char, kind = cell
                    twinkle = 0.5 + 0.5 * math.sin(
                        motion_t * (0.10 if kind == "star" else 0.16 * style.twinkle_rate)
                        + x * 0.71
                        + y * 0.23
                        + scene_seed * 1.9
                    )
                    boost = row_breath
                    if kind in {"accent", "warm_accent", "beam"}:
                        boost += phase_boost * 0.7
                    if kind in {"seed", "thread", "bloom", "glow"}:
                        boost += 0.35 + phase_boost * 0.9
                    if kind in {"window", "reflection_window"} and twinkle < 0.08 and fade < 0.6:
                        base_char = " "
                    char = base_char
                    color = self._kind_color(city_name, kind, boost, fade, twinkle)

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

    def _render_city_display(self, city_name: str, now: float, phase: str, progress: float) -> str:
        scene = self._scene(city_name)
        canvas = self._compose_city_canvas(city_name, scene, now, phase, progress)
        return self._render_canvas(city_name, canvas, now, phase=phase, progress=progress)

    def _transition_mix(self, progress: float) -> float:
        return self._ease_in_out(progress)

    def _build_transition_canvas(
        self,
        from_canvas: list[list[tuple[int, str, str] | None]],
        to_canvas: list[list[tuple[int, str, str] | None]],
        data: dict,
        progress: float,
    ) -> list[list[tuple[int, str, str] | None]]:
        canvas: list[list[tuple[int, str, str] | None]] = [[None] * self.width for _ in range(self.height)]
        mix = self._transition_mix(progress)
        seam = data["seam_width"]

        for y in range(self.height):
            for x in range(self.width):
                from_cell = from_canvas[y][x]
                to_cell = to_canvas[y][x]
                if from_cell is None and to_cell is None:
                    continue

                threshold = data["thresholds"][y][x]
                delta = mix - threshold

                if delta <= -seam:
                    if from_cell is not None:
                        canvas[y][x] = from_cell
                    elif to_cell is not None and threshold - mix <= seam * 1.4:
                        canvas[y][x] = (to_cell[0], to_cell[1], "glow")
                    continue

                if delta >= seam:
                    if to_cell is not None:
                        canvas[y][x] = to_cell
                    elif from_cell is not None and mix - threshold <= seam * 1.4:
                        canvas[y][x] = (from_cell[0], from_cell[1], "glow")
                    continue

                preferred = to_cell if mix >= threshold and to_cell is not None else from_cell
                if preferred is None:
                    preferred = to_cell if to_cell is not None else from_cell
                if preferred is not None:
                    canvas[y][x] = (preferred[0] + 1, preferred[1], "glow")
        return canvas

    def _transition_canvas(self, city_name: str, next_city: str, now: float, progress: float) -> list[list[tuple[int, str, str] | None]]:
        data = self._transition_data
        if data is None or self._next_city != next_city:
            data = self._build_transition_scene(city_name, next_city)
        from_canvas = self._compose_city_canvas(city_name, data["from_scene"], now, "transition", progress)
        to_canvas = self._compose_city_canvas(next_city, data["to_scene"], now, "transition", progress)
        return self._build_transition_canvas(from_canvas, to_canvas, data, progress)

    def _render_transition_frame(self, city_name: str, next_city: str, phase: str, progress: float, now: float) -> str:
        data = self._transition_data
        if data is None:
            return self._render_city_display(city_name, now, "city_display", 0.0)
        canvas = self._transition_canvas(city_name, next_city, now, progress)
        palette_city = city_name if progress < 0.5 else next_city
        seam_emphasis = 0.08 + 0.18 * (1.0 - abs(0.5 - progress) * 2.0)
        return self._render_canvas(
            palette_city,
            canvas,
            now,
            phase=phase,
            progress=progress,
            phase_boost=seam_emphasis,
        )

    def render_frame(self) -> str:
        now = self._time_source()
        city_name, next_city, phase, progress = self._stage(now)
        if phase == "city_display" or next_city is None:
            return self._render_city_display(city_name, now, phase, progress)
        return self._render_transition_frame(city_name, next_city, phase, progress, now)
