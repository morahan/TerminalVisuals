import math
import random

from src.base import BaseVisualizer, Slider, CHAR_ASPECT


class DysonVisualizer(BaseVisualizer):
    """Dyson swarm — satellites accumulate into orbiting rings, layer by layer."""

    CHARS = {
        "sat": "\u2502",        # │
        "sat_ascii": "|",
        "core": "\u25cf",       # ●
        "core_ascii": "*",
        "star": "\u00b7",       # ·
        "star_ascii": ".",
    }

    sliders = [
        Slider(name="Spread", attr="spread", min_val=0.10, max_val=0.60, step=0.05, fmt=".2f"),
        Slider(name="Orbit", attr="orbit_speed", min_val=0.5, max_val=3.0, step=0.25),
    ]

    SATS_PER_RING = 18
    SPAWN_INTERVAL = 8
    MAX_RINGS = 5

    PALETTE = [
        ("96;1", "36", "2;36"),   # cyan
        ("97;1", "37", "2;37"),   # white
        ("94;1", "34", "2;34"),   # blue
        ("95;1", "35", "2;35"),   # magenta
        ("93;1", "33", "2;33"),   # yellow
    ]

    RING_ORBITS = [
        (0.0,              1.0),
        (math.pi / 3,     -0.80),
        (2 * math.pi / 3,  0.65),
        (math.pi / 2,     -0.50),
        (5 * math.pi / 6,  0.45),
    ]

    def __init__(
        self,
        size: int = 0,
        speed: int = 5,
        brightness: int = 100,
        ascii_mode: bool = False,
        oneshot: bool = False,
        spread: float = 0.30,
        orbit_speed: float = 1.5,
    ):
        super().__init__(size, speed, brightness, ascii_mode, oneshot)
        self.spread = spread
        self.orbit_speed = orbit_speed
        self.stars = self._generate_stars()
        self._trail: dict[tuple[int, int], int] = {}  # (y, x) -> ring_idx

    def reset(self) -> None:
        super().reset()
        self._trail.clear()

    def _on_resize(self) -> None:
        self.stars = self._generate_stars()
        self._trail.clear()

    def _generate_stars(self) -> dict[tuple[int, int], float]:
        stars = {}
        random.seed(77)
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

    def _project(
        self, theta: float, alpha: float, beta: float, R: float, cx: float, cy: float
    ) -> tuple[int, int, float]:
        """Project orbital point to screen. Returns (screen_x, screen_y, z_depth)."""
        x = R * math.cos(theta)
        z = R * math.sin(theta)

        sin_a, cos_a = math.sin(alpha), math.cos(alpha)
        sin_b, cos_b = math.sin(beta), math.cos(beta)

        y_rot = -z * sin_a
        z_rot = z * cos_a
        x_final = x * cos_b + z_rot * sin_b
        z_final = -x * sin_b + z_rot * cos_b

        screen_x = int(round(cx + x_final))
        screen_y = int(round(cy + y_rot * CHAR_ASPECT))
        return screen_x, screen_y, z_final

    def render_frame(self) -> str:
        cx = self.width / 2.0
        cy = self.height / 2.0
        R = min(self.width * 0.42, self.height / CHAR_ASPECT * 0.42)

        max_sats = self.MAX_RINGS * self.SATS_PER_RING
        total_spawned = int(min(self.frame // self.SPAWN_INTERVAL + 1, max_sats))

        direction = -1 if self.reversed else 1

        cam_a = 0.005 * math.sin(self.frame * 0.009)
        cam_b = 0.003 * math.sin(self.frame * 0.006)

        dim = self.brightness < 50
        core_x = int(round(cx))
        core_y = int(round(cy))

        # Collect satellite positions
        points = []
        spawned = 0
        for ring_idx in range(self.MAX_RINGS):
            ring_count = min(self.SATS_PER_RING, total_spawned - spawned)
            if ring_count <= 0:
                break

            base_alpha = 0.20 + ring_idx * self.spread
            beta_off, speed_mult = self.RING_ORBITS[ring_idx]
            alpha = base_alpha + cam_a
            beta = beta_off + cam_b

            for s in range(ring_count):
                base_angle = s * 2 * math.pi / self.SATS_PER_RING
                theta = base_angle + self.frame * 0.02 * self.orbit_speed * speed_mult * direction

                sx, sy, z = self._project(theta, alpha, beta, R, cx, cy)
                spawn_frame = (spawned + s) * self.SPAWN_INTERVAL
                age = self.frame - spawn_frame
                points.append((sx, sy, z, ring_idx, age))

            spawned += ring_count

        # Update persistent trail (only grows, never shrinks)
        for sx, sy, z, ring_idx, age in points:
            if 0 <= sx < self.width and 0 <= sy < self.height:
                self._trail[(sy, sx)] = ring_idx

        # Sort active satellites back-to-front for layering
        points.sort(key=lambda p: p[2])

        # Build grid
        grid: list[list[str]] = [[" "] * self.width for _ in range(self.height)]

        # Layer 1: background stars
        star_char = self._get_char("star")
        for (y, x), seed in self.stars.items():
            if 0 <= y < self.height and 0 <= x < self.width:
                sc = self._color("90") if seed > 0.92 and not dim else self._color("2;90")
                grid[y][x] = f"{sc}{star_char}{self.ANSI_RESET}"

        # Layer 2: persistent trail (dim │ — the orbital path memory)
        sat_char = self._get_char("sat")
        for (y, x), ring_idx in self._trail.items():
            if 0 <= y < self.height and 0 <= x < self.width:
                _, _, dim_c = self.PALETTE[ring_idx % len(self.PALETTE)]
                color = self._color("2;90") if dim else self._color(dim_c)
                grid[y][x] = f"{color}{sat_char}{self.ANSI_RESET}"

        # Layer 3: active satellites (bright, overwrite trail at current positions)
        for sx, sy, z, ring_idx, age in points:
            if not (0 <= sx < self.width and 0 <= sy < self.height):
                continue
            if z < 0 and sx == core_x and sy == core_y:
                continue

            bright_c, normal_c, dim_c = self.PALETTE[ring_idx % len(self.PALETTE)]

            if age < 10:
                # New satellite: bright pop, then settles
                color = self._color(bright_c) if not dim else self._color(normal_c)
            elif z < 0:
                # Behind: visible but subdued (brighter than trail so it's distinct)
                color = self._color(normal_c) if not dim else self._color(dim_c)
            else:
                # Front: full brightness
                color = self._color(bright_c) if not dim else self._color(normal_c)

            grid[sy][sx] = f"{color}{sat_char}{self.ANSI_RESET}"

        # Layer 4: central star (always on top)
        if 0 <= core_y < self.height and 0 <= core_x < self.width:
            cc = self._color("97;1") if not dim else self._color("37")
            grid[core_y][core_x] = f"{cc}{self._get_char('core')}{self.ANSI_RESET}"

        lines = ["".join(row) for row in grid]
        return "\n".join(lines) + f"\033[{self.height + 1};1H"
