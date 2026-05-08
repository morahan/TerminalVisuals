import math
import random

from src.base import BaseVisualizer, Slider


class EmberVisualizer(BaseVisualizer):
    """Embers and flame — a continuous heat field with rising tongues and floating sparks."""

    CHARS = {
        "peak":       "●",   # ●
        "bright":     "◆",   # ◆
        "medium":     "•",   # •
        "dim":        "·",   # ·
        "glow_heavy": "▓",   # ▓
        "glow_mid":   "▒",   # ▒
        "glow_light": "░",   # ░
        "ember_hot":  "∙",   # ∙
        "ember_warm": "·",   # ·
        "spark":      "*",
        "trail":      "'",
        "peak_ascii":       "O",
        "bright_ascii":     "*",
        "medium_ascii":     "o",
        "dim_ascii":        ".",
        "glow_heavy_ascii": "#",
        "glow_mid_ascii":   "=",
        "glow_light_ascii": "-",
        "ember_hot_ascii":  "^",
        "ember_warm_ascii": ".",
        "spark_ascii":      "*",
        "trail_ascii":      "^",
    }

    sliders = [
        Slider(name="Density", attr="density", min_val=20, max_val=200, step=10, fmt="d"),
        Slider(name="Warmth", attr="warmth", min_val=0.5, max_val=3.0, step=0.25),
        Slider(name="Turbulence", attr="turbulence", min_val=0.5, max_val=3.0, step=0.25),
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
        turbulence: float = 1.0,
    ):
        super().__init__(size, speed, brightness, ascii_mode, oneshot)
        self.density = density
        self.warmth = warmth
        self.turbulence = turbulence
        self._seed_embers()

    def _seed_embers(self) -> None:
        random.seed(55)
        self.embers = []
        for _ in range(250):
            self.embers.append({
                "base_x": random.random(),
                "rise_speed": 0.3 + random.random() * 0.8,
                "y_offset": random.random(),
                "wobble_freq": 0.4 + random.random() * 1.2,
                "wobble_amp": 0.3 + random.random() * 1.5,
                "wobble_phase": random.random() * math.pi * 2,
                "pulse_freq": 0.3 + random.random() * 0.6,
                "pulse_phase": random.random() * math.pi * 2,
                "size_seed": random.random(),
                "heat": 0.5 + random.random() * 0.5,
            })

    def _get_char(self, name: str) -> str:
        if self.ascii_mode:
            key = f"{name}_ascii"
            return self.CHARS.get(key, self.CHARS.get(name, " "))
        return self.CHARS.get(name, " ")

    def _color(self, code: str) -> str:
        return f"\033[{code}m"

    def _fire_color(self, heat: float) -> str:
        """Color for flame at given heat level (0=cool, 1=hot)."""
        dim = self.brightness < 50
        if heat > 0.92 and self.brightness >= 100:
            return "97"  # white-hot core
        elif heat > 0.78:
            return "93" if not dim else "2;93"  # yellow
        elif heat > 0.58:
            return "33" if not dim else "2;33"  # orange
        elif heat > 0.38:
            return "91" if not dim else "2;91"  # light red
        elif heat > 0.18:
            return "31" if not dim else "2;31"  # red
        else:
            return "2;31"  # dim red

    def _fire_char(self, heat: float) -> str:
        """Character for flame body, chosen by heat. Cooler heats use soft block glyphs."""
        if heat > 0.85:
            return self._get_char("peak")
        if heat > 0.68:
            return self._get_char("bright")
        if heat > 0.50:
            return self._get_char("medium")
        if heat > 0.32:
            return self._get_char("glow_heavy")
        if heat > 0.20:
            return self._get_char("glow_mid")
        return self._get_char("glow_light")

    def _ember_color(self, heat: float) -> str:
        """Color for ember particle at given heat."""
        dim = self.brightness < 50
        if heat > 0.8 and self.brightness >= 100:
            return "97"
        elif heat > 0.65:
            return "93" if not dim else "2;33"
        elif heat > 0.45:
            return "33" if not dim else "2;33"
        elif heat > 0.25:
            return "31" if not dim else "2;31"
        else:
            return "2;31"

    def _ember_char(self, heat: float) -> str:
        if heat > 0.75:
            return self._get_char("spark")
        elif heat > 0.4:
            return self._get_char("ember_hot")
        return self._get_char("ember_warm")

    def render_frame(self) -> str:
        w, h = self.width, self.height
        grid: list[list[str]] = [[" " for _ in range(w)] for _ in range(h)]
        t = self.frame * 0.12

        # === HEAT FIELD ===
        # Continuous flame body. For each cell compute a heat value driven by:
        #   - vertical base profile (hot at bottom, fading up),
        #   - low-frequency horizontal warmth that wanders over time,
        #   - multi-octave noise producing rising tongues.
        warmth = self.warmth
        turb = self.turbulence
        # warmth boosts vertical reach: higher warmth pushes heat further up.
        reach = 0.45 + 0.55 * warmth  # ~0.7 .. ~2.1
        heat_field: list[list[float]] = [[0.0] * w for _ in range(h)]

        for y in range(h):
            # Vertical profile: 1 at bottom (large y), 0 at top, lifted by warmth.
            v = y / max(1, h - 1)
            base = (v ** (2.0 / max(0.6, reach)))

            # Tongues lean/curl as they rise — phase grows as we move upward
            # (i.e. toward y=0). dy_top is distance from the top of the screen.
            dy_top = (h - 1 - y)
            y_phase = dy_top * 0.35

            for x in range(w):
                # Slow wandering horizontal warmth — a couple of broad hot spots
                # drift across the bed without ever forming a flat stripe.
                hw = (
                    0.55
                    + 0.30 * math.sin(x * 0.045 + t * 0.45)
                    + 0.15 * math.sin(x * 0.11 - t * 0.27 + 1.7)
                )

                # Multi-octave turbulence — these are the rising flame tongues.
                # Higher octaves carry less weight; vertical phase rise makes
                # them appear to lick upward as t advances.
                n1 = math.sin(x * 0.18 + y_phase + t * 1.10)
                n2 = math.sin(x * 0.37 - y_phase * 0.7 + t * 1.65 + 2.1)
                n3 = math.sin(x * 0.71 + y_phase * 1.3 - t * 2.30 + 0.7)
                noise = (n1 * 0.55 + n2 * 0.30 + n3 * 0.15)

                # Combine. Noise is centred around 0 and weighted toward the
                # top (where base is fading) so it carves the upper flame edge
                # into ragged tongues without disturbing the hot base.
                heat = base * hw + noise * 0.42 * (1.0 - v) * turb
                # Subtle global flicker to keep the body alive even when still.
                heat *= 0.92 + 0.08 * math.sin(t * 1.9 + x * 0.05)

                if heat < 0.0:
                    heat = 0.0
                elif heat > 1.0:
                    heat = 1.0
                heat_field[y][x] = heat

        # === RENDER FLAME BODY ===
        # Threshold below which we leave the cell empty — this gives the top
        # of the flame ragged, organic edges and prevents any solid row.
        for y in range(h):
            row = heat_field[y]
            for x in range(w):
                heat = row[x]
                if heat < 0.18:
                    continue
                char = self._fire_char(heat)
                code = self._fire_color(heat)
                grid[y][x] = f"{self._color(code)}{char}{self.ANSI_RESET}"

        # === COAL BED ===
        # Bottom 1–2 rows: probabilistic bright embers where the heat field is
        # hottest, with per-cell flicker. Probabilistic + flicker means the row
        # is never fully filled, so it reads as glowing coals — never a bar.
        coal_rows = 1 if h < 14 else 2
        for cy in range(h - coal_rows, h):
            if cy < 0:
                continue
            for cx in range(w):
                heat = heat_field[cy][cx]
                if heat < 0.55:
                    continue
                flicker = 0.5 + 0.5 * math.sin(cx * 0.43 + t * 2.7 + cy * 1.1)
                if flicker < 0.35:
                    continue
                hot = min(1.0, heat * (0.7 + 0.5 * flicker))
                if hot > 0.85:
                    char = self._get_char("ember_hot")
                else:
                    char = self._get_char("glow_heavy")
                code = self._fire_color(hot)
                grid[cy][cx] = f"{self._color(code)}{char}{self.ANSI_RESET}"

        # === FLYING EMBERS ===
        # Embers always rise. They're suppressed inside the dense flame body
        # (where they'd be invisible anyway) and only emit trails above the
        # smoke line so they don't smear the bright core.
        count = int(self.density)
        for idx in range(min(count, len(self.embers))):
            e = self.embers[idx]

            # Vertical: rises upward with deceleration.
            y_norm = (1.0 - (self.frame * 0.006 * e["rise_speed"] + e["y_offset"])) % 1.0
            y = int(y_norm * (h - 2))
            if y < 0 or y >= h:
                continue

            # Horizontal wobble — this is what `reverse` flips, so the embers
            # drift the other way without breaking gravity.
            wobble_dir = -1 if self.reversed else 1
            wobble = (
                math.sin(self.frame * 0.04 * e["wobble_freq"] + e["wobble_phase"]) * e["wobble_amp"]
                + math.sin(self.frame * 0.02 * e["wobble_freq"] * 1.3) * e["wobble_amp"] * 0.5 * self.turbulence
            ) * wobble_dir
            x = int(e["base_x"] * w + wobble) % w

            # Skip embers buried in the dense flame body — keeps things readable.
            if heat_field[y][x] > 0.55:
                continue

            heat = max(0.0, e["heat"] - y_norm * 0.6)
            raw_pulse = math.sin(self.frame * 0.04 * e["pulse_freq"] + e["pulse_phase"])
            brightness_val = raw_pulse * raw_pulse
            combined = brightness_val * (0.4 + 0.6 * e["size_seed"]) * (0.3 + 0.7 * heat)
            if combined < 0.06 or heat < 0.05:
                continue

            char = self._ember_char(combined * heat)
            code = self._ember_color(heat * combined)
            grid[y][x] = f"{self._color(code)}{char}{self.ANSI_RESET}"

            # Trails only outside the flame body.
            if combined > 0.3 and heat > 0.3:
                trail_len = int(2 + 3 * heat * combined)
                for ti in range(1, trail_len + 1):
                    ty = y + ti
                    if ty >= h:
                        break
                    tx = (x + int(wobble * 0.1 * ti)) % w
                    if heat_field[ty][tx] > 0.35:
                        break
                    trail_heat = heat * (1.0 - ti / (trail_len + 1)) * 0.6
                    if trail_heat < 0.08:
                        break
                    if grid[ty][tx] == " ":
                        trail_char = self._get_char("trail")
                        trail_code = self._ember_color(trail_heat * 0.7)
                        grid[ty][tx] = f"{self._color(trail_code)}{trail_char}{self.ANSI_RESET}"

        lines = ["".join(row) for row in grid]
        return "\n".join(lines) + f"\033[{h + 1};1H"
