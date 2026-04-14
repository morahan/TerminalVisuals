import math

from src.base import BaseVisualizer, Slider


class ZenVisualizer(BaseVisualizer):
    """Zen sand garden -- a rake glides through the sand, leaving settling grooves."""

    sliders = [
        Slider(name="Rake", attr="rake_width", min_val=1, max_val=5, step=1, fmt="d"),
        Slider(name="Detail", attr="level", min_val=2, max_val=5, step=1, fmt="d"),
    ]

    CHARS = {
        "sand": "\u00b7",       # ·
        "horiz": "\u2500",      # ─
        "vert": "\u2502",       # │
        "head": "\u25e6",       # ◦
        "sand_ascii": ".",
        "horiz_ascii": "-",
        "vert_ascii": "|",
        "head_ascii": "o",
    }

    # Pre-computed age color codes
    _AGE_COLORS = ["97;1", "97", "93", "33", "2;33", "90"]
    _AGE_COLORS_DIM = ["97", "97", "93", "33", "2;33", "90"]
    _AGE_THRESHOLDS = [0.03, 0.10, 0.25, 0.50, 0.75]
    _SAMPLE_DENSITY = 2.4

    def __init__(
        self,
        size: int = 0,
        speed: int = 5,
        brightness: int = 100,
        ascii_mode: bool = False,
        oneshot: bool = False,
        rake_width: int = 3,
        level: int = 4,
    ):
        super().__init__(size, speed, brightness, ascii_mode, oneshot)
        self.rake_width = rake_width
        self.level = level
        self._built_level = -1
        self._path: list[tuple[int, int]] = []
        self._directions: list[tuple[int, int]] = []
        self._curve_size = 0
        self._sample_footprints: list[list[tuple[int, int, str]]] = []
        self._sample_heads: list[tuple[int, int, str] | None] = []
        self._sand_rows: list[str] = []
        self._sand_colors: list[str] = []
        self._cache_key: tuple = ()
        self._build_path()

    @staticmethod
    def _hilbert_d2xy(n: int, d: int) -> tuple[int, int]:
        """Convert distance d along a Hilbert curve to (x, y) in an n x n grid."""
        x = y = 0
        s = 1
        while s < n:
            rx = 1 & (d // 2)
            ry = 1 & (d ^ rx)
            if ry == 0:
                if rx == 1:
                    x = s - 1 - x
                    y = s - 1 - y
                x, y = y, x
            x += s * rx
            y += s * ry
            d //= 4
            s *= 2
        return x, y

    def _build_path(self) -> None:
        """Pre-compute Hilbert curve path and per-segment directions."""
        n = 2 ** self.level
        self._curve_size = n
        total = n * n
        self._path = [self._hilbert_d2xy(n, d) for d in range(total)]
        self._directions = []
        for i in range(total):
            if i + 1 < total:
                dx = self._path[i + 1][0] - self._path[i][0]
                dy = self._path[i + 1][1] - self._path[i][1]
            else:
                dx = self._path[i][0] - self._path[i - 1][0]
                dy = self._path[i][1] - self._path[i - 1][1]
            self._directions.append((dx, dy))
        self._built_level = self.level
        self._cache_key = ()  # invalidate segment cache

    def _sample_footprint(
        self,
        center_x: float,
        center_y: float,
        dx: float,
        dy: float,
        w: int,
        h: int,
    ) -> list[tuple[int, int, str]]:
        half = self.rake_width // 2
        base_x = int(round(center_x))
        base_y = int(round(center_y))
        seen: set[tuple[int, int]] = set()
        cells: list[tuple[int, int, str]] = []

        is_horiz = abs(dx) >= abs(dy)
        ch = self._get_char("horiz" if is_horiz else "vert")

        if is_horiz:
            for offset in range(-half, half + 1):
                x = base_x
                y = base_y + offset
                if 0 <= x < w and 0 <= y < h and (x, y) not in seen:
                    cells.append((x, y, ch))
                    seen.add((x, y))
        else:
            for offset in range(-half, half + 1):
                x = base_x + offset
                y = base_y
                if 0 <= x < w and 0 <= y < h and (x, y) not in seen:
                    cells.append((x, y, ch))
                    seen.add((x, y))

        return cells

    def _build_samples(self) -> None:
        """Pre-compute terminal rake samples for a smooth pass through the garden."""
        w, h = self.width, self.height
        n = self._curve_size
        total = len(self._path)

        pad_x = max(1, w // 24)
        pad_y = max(1, h // 12)
        usable_w = max(1, w - 1 - pad_x * 2)
        usable_h = max(1, h - 1 - pad_y * 2)
        ox = pad_x
        oy = pad_y
        sx = usable_w / max(1, n - 1)
        sy = usable_h / max(1, n - 1)

        control_points = [
            (ox + gx * sx, oy + gy * sy)
            for gx, gy in self._path
        ]

        self._sample_footprints = []
        self._sample_heads = []
        head_ch = self._get_char("head")

        for i in range(total - 1):
            x1, y1 = control_points[i]
            x2, y2 = control_points[i + 1]
            dx = x2 - x1
            dy = y2 - y1

            steps = max(1, int(math.ceil(max(abs(dx), abs(dy)) * self._SAMPLE_DENSITY)))
            start = 0 if i == 0 else 1

            for step in range(start, steps + 1):
                u = step / steps
                cx = x1 + dx * u
                cy = y1 + dy * u
                footprint = self._sample_footprint(cx, cy, dx, dy, w, h)
                if not footprint:
                    continue

                self._sample_footprints.append(footprint)
                hx = int(round(cx))
                hy = int(round(cy))
                if 0 <= hx < w and 0 <= hy < h:
                    self._sample_heads.append((hx, hy, head_ch))
                else:
                    self._sample_heads.append(None)

        sand_dot = self._get_char("sand")
        self._sand_rows = []
        self._sand_colors = []
        for y in range(h):
            row_ratio = y / max(1, h - 1)
            band = 0.5 + 0.5 * math.sin(row_ratio * math.pi * 2.6 - 0.35)
            freq = 0.070 + 0.018 * math.cos(row_ratio * math.pi * 1.7)
            threshold = 0.974 + 0.008 * (1.0 - band)
            sand_chars = []
            for x in range(w):
                ripple = 0.5 + 0.5 * math.sin(x * freq + y * 0.42)
                drift = 0.5 + 0.5 * math.sin(x * (freq * 0.36) - y * 0.24)
                if ripple * 0.76 + drift * 0.24 > threshold:
                    sand_chars.append(sand_dot)
                else:
                    sand_chars.append(" ")
            self._sand_rows.append("".join(sand_chars))
            if band > 0.58 and self.brightness >= 50:
                self._sand_colors.append("\033[33m")
            elif band > 0.42:
                self._sand_colors.append("\033[2;33m")
            else:
                self._sand_colors.append("\033[90m")

        self._cache_key = (w, h, self.rake_width, self.level, self.ascii_mode, self.brightness)

    def _get_char(self, name: str) -> str:
        if self.ascii_mode:
            return self.CHARS.get(f"{name}_ascii", self.CHARS.get(name, " "))
        return self.CHARS.get(name, " ")

    def _age_color_code(self, ratio: float) -> str:
        """Return ANSI color escape for groove age (0 = fresh, 1+ = old)."""
        codes = self._AGE_COLORS_DIM if self.brightness < 50 else self._AGE_COLORS
        for j, thresh in enumerate(self._AGE_THRESHOLDS):
            if ratio < thresh:
                return codes[j]
        return codes[-1]

    def _render_sand(self) -> str:
        reset = self.ANSI_RESET
        lines = []
        for y, row in enumerate(self._sand_rows):
            lines.append(f"{self._sand_colors[y]}{row}{reset}")
        return "\n".join(lines) + f"\n\033[{self.height + 1};1H"

    def render_frame(self) -> str:
        if self._built_level != self.level:
            self._build_path()

        w, h = self.width, self.height
        key = (w, h, self.rake_width, self.level, self.ascii_mode, self.brightness)
        if self._cache_key != key:
            self._build_samples()

        sample_total = len(self._sample_footprints)
        if sample_total == 0:
            return self._render_sand()

        sweep_rate = max(5.0, sample_total / 72.0)
        t_sweep = sample_total / sweep_rate
        t_hold = 12.0
        t_fade = 26.0
        cycle = t_sweep + t_hold + t_fade

        t = self.frame % cycle
        if t < t_sweep:
            head_idx = min(sample_total - 1, int(t * sweep_rate))
            carved = head_idx + 1
            settle_bias = 0.02
            fade = 0.0
            show_head = True
        elif t < t_sweep + t_hold:
            head_idx = sample_total - 1
            carved = sample_total
            settle_bias = 0.28
            fade = 0.0
            show_head = False
        else:
            head_idx = sample_total - 1
            carved = sample_total
            settle_bias = 0.46
            fade = (t - t_sweep - t_hold) / t_fade
            show_head = False

        grid: list[list[tuple[str, str] | None]] = [[None] * w for _ in range(h)]
        trail_span = max(22.0, sample_total * 0.24)
        inv_trail = 1.0 / trail_span

        for i in range(carved):
            age = (carved - 1 - i) * inv_trail * 0.78 + settle_bias + fade * 0.92
            color = f"\033[{self._age_color_code(age)}m"
            for x, y, ch in self._sample_footprints[i]:
                grid[y][x] = (ch, color)

        if show_head:
            hc = self._sample_heads[head_idx]
            if hc is not None:
                hx, hy, hch = hc
                head_color = "\033[97m" if self.brightness < 50 else "\033[97;1m"
                grid[hy][hx] = (hch, head_color)

        reset = self.ANSI_RESET

        lines = []
        for y, row in enumerate(grid):
            parts = []
            prev_col = None
            sand_row = self._sand_rows[y]
            sand_col = self._sand_colors[y]
            for x, cell in enumerate(row):
                if cell is None:
                    c, col = sand_row[x], sand_col
                else:
                    c, col = cell
                if col != prev_col:
                    parts.append(col)
                    prev_col = col
                parts.append(c)
            parts.append(reset)
            lines.append("".join(parts))

        return "\n".join(lines) + f"\n\033[{h + 1};1H"
