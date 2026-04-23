import math
import random

from src.base import BaseVisualizer, Slider


class EmberVisualizer(BaseVisualizer):
    """Embers and flame — dynamic fire with dancing columns and flying sparks."""

    CHARS = {
        "peak":       "\u25cf",   # ●
        "bright":     "\u25c6",   # ◆
        "medium":     "\u2022",   # •
        "dim":        "\u00b7",   # ·
        "glow_heavy": "\u2593",   # ▓
        "glow_mid":   "\u2592",   # ▒
        "glow_light": "\u2591",   # ░
        "ember_hot":  "\u2219",   # ∙
        "ember_warm": "\u00b7",   # ·
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
        self._seed_flames()
        self._seed_embers()

    def _seed_flames(self) -> None:
        random.seed(77)
        self.flames = []
        for _ in range(40):
            self.flames.append({
                "base_x": random.random(),
                "sway_freq": 0.3 + random.random() * 0.5,
                "sway_phase": random.random() * math.pi * 2,
                "sway_amp": 0.3 + random.random() * 0.7,
                "flicker_freq": 0.5 + random.random() * 0.8,
                "flicker_phase": random.random() * math.pi * 2,
                "height_mult": 0.5 + random.random() * 0.5,
                "width": 0.03 + random.random() * 0.04,
            })

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
        if heat > 0.9 and self.brightness >= 100:
            return "97"  # white
        elif heat > 0.75:
            return "93" if not dim else "2;93"  # yellow
        elif heat > 0.55:
            return "33" if not dim else "2;33"  # orange
        elif heat > 0.35:
            return "91" if not dim else "2;91"  # light red
        elif heat > 0.15:
            return "31" if not dim else "2;31"  # red
        else:
            return "2;31"  # dim red

    def _fire_char(self, heat: float, edge: float) -> str:
        """Character for flame: heat controls brightness, edge (0=center, 1=edge)."""
        if heat > 0.8 and edge < 0.3:
            return self._get_char("peak")
        elif heat > 0.6 and edge < 0.5:
            return self._get_char("bright")
        elif heat > 0.4:
            return self._get_char("medium")
        return self._get_char("dim")

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
        direction = -1 if self.reversed else 1

        # === GROUND GLOW ===
        ground_rows = min(4, max(2, h // 5))
        t = self.frame * self.turbulence
        for gy in range(h - ground_rows, h):
            depth = h - gy
            for gx in range(w):
                # Chaotic flickering
                glow_val = (
                    0.4
                    + 0.3 * math.sin(gx * 0.12 + t * 0.08)
                    + 0.15 * math.sin(gx * 0.31 - t * 0.05)
                    + 0.1 * math.sin(gx * 0.07 + t * 0.13)
                    + 0.05 * math.sin(gx * 0.5 + t * 0.2)
                )
                if glow_val < 0.25:
                    continue
                intensity = glow_val * (depth / ground_rows)
                if depth == 1:
                    char = self._get_char("glow_heavy")
                    code = "33" if self.brightness >= 50 else "2;33"
                elif depth == 2:
                    char = self._get_char("glow_mid")
                    code = "31" if intensity > 0.5 else "2;31"
                elif depth == 3:
                    char = self._get_char("glow_light")
                    code = "2;31" if intensity > 0.4 else "2;2;31"
                else:
                    char = self._get_char("glow_light")
                    code = "2;2;31"
                grid[gy][gx] = f"{self._color(code)}{char}{self.ANSI_RESET}"

        # === FLAME COLUMNS ===
        flame_height = int((h - ground_rows) * 0.35 * self.warmth)
        num_flames = min(35, max(8, int(w * 0.08 * self.warmth)))

        for fi, fl in enumerate(self.flames[:num_flames]):
            # Swaying center x
            sway = (
                math.sin(t * fl["sway_freq"] + fl["sway_phase"]) * fl["sway_amp"] * self.turbulence
                + math.sin(t * fl["sway_freq"] * 1.7 + fl["sway_phase"] * 0.7) * fl["sway_amp"] * 0.5 * self.turbulence
            )
            cx = int((fl["base_x"] + sway * 0.01) * w) % w

            # Flicker intensity for this flame
            flicker = 0.6 + 0.4 * (
                math.sin(t * fl["flicker_freq"] * 2.3 + fl["flicker_phase"]) ** 2
                * math.sin(t * fl["flicker_freq"] * 0.7 + fl["flicker_phase"] * 1.3)
            )
            flicker = max(0.2, min(1.0, flicker))

            fheight = int(flame_height * fl["height_mult"] * flicker)
            half_w = int(fl["width"] * w * self.warmth * flicker)
            half_w = max(1, half_w)

            for dy in range(fheight):
                gy = h - ground_rows - 1 - dy
                if gy < 0:
                    break
                # Heat decreases with height
                heat = 1.0 - (dy / max(1, fheight)) ** 1.5
                heat *= flicker

                # Gaussian-ish horizontal profile
                for dx in range(-half_w, half_w + 1):
                    gx = (cx + dx) % w
                    dist = abs(dx) / max(1, half_w)
                    edge_factor = dist ** 1.5
                    cell_heat = heat * (1.0 - edge_factor * 0.6)

                    if cell_heat < 0.08:
                        continue

                    char = self._fire_char(cell_heat, edge_factor)
                    code = self._fire_color(cell_heat)
                    grid[gy][gx] = f"{self._color(code)}{char}{self.ANSI_RESET}"

        # === FLYING EMBERS ===
        count = int(self.density)
        for idx in range(min(count, len(self.embers))):
            e = self.embers[idx]

            # Vertical: rises upward with deceleration
            y_norm = (1.0 - (self.frame * 0.006 * e["rise_speed"] * direction + e["y_offset"])) % 1.0
            y = int(y_norm * (h - 2))
            if y < 0 or y >= h - ground_rows:
                continue

            # Horizontal wobble with turbulence
            wobble = (
                math.sin(self.frame * 0.04 * e["wobble_freq"] + e["wobble_phase"]) * e["wobble_amp"]
                + math.sin(self.frame * 0.02 * e["wobble_freq"] * 1.3) * e["wobble_amp"] * 0.5 * self.turbulence
            )
            x = int(e["base_x"] * w + wobble) % w

            # Heat decay as it rises
            heat = max(0.0, e["heat"] - y_norm * 0.6)

            # Pulse
            raw_pulse = math.sin(self.frame * 0.04 * e["pulse_freq"] + e["pulse_phase"])
            brightness_val = raw_pulse * raw_pulse
            combined = brightness_val * (0.4 + 0.6 * e["size_seed"]) * (0.3 + 0.7 * heat)

            if combined < 0.06 or heat < 0.05:
                continue

            # Draw ember
            char = self._ember_char(combined * heat)
            code = self._ember_color(heat * combined)
            grid[y][x] = f"{self._color(code)}{char}{self.ANSI_RESET}"

            # Trail for brighter, hotter embers
            if combined > 0.3 and heat > 0.3:
                trail_len = int(2 + 3 * heat * combined)
                for ti in range(1, trail_len + 1):
                    ty = y + ti
                    if ty >= h - ground_rows:
                        break
                    trail_heat = heat * (1.0 - ti / (trail_len + 1)) * 0.6
                    if trail_heat < 0.08:
                        break
                    tx = (x + int(wobble * 0.1 * ti)) % w
                    trail_char = self._get_char("trail")
                    trail_code = self._ember_color(trail_heat * 0.7)
                    if grid[ty][tx] == " ":
                        grid[ty][tx] = f"{self._color(trail_code)}{trail_char}{self.ANSI_RESET}"

        lines = []
        for row in grid:
            lines.append("".join(row))
        return "\n".join(lines) + f"\033[{h + 1};1H"
