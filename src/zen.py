import math

from src.base import BaseVisualizer, Slider


class ZenVisualizer(BaseVisualizer):
    """Zen sand garden -- a rake traces a Hilbert curve, leaving parallel grooves."""

    sliders = [
        Slider(name="Rake", attr="rake_width", min_val=1, max_val=5, step=1, fmt="d"),
        Slider(name="Detail", attr="level", min_val=2, max_val=5, step=1, fmt="d"),
    ]

    CHARS = {
        "sand": "\u00b7",       # ·
        "horiz": "\u2500",      # ─
        "vert": "\u2502",       # │
        "corner_dr": "\u256d",  # ╭
        "corner_dl": "\u256e",  # ╮
        "corner_ur": "\u2570",  # ╰
        "corner_ul": "\u256f",  # ╯
        "head": "\u25e6",       # ◦
        "sand_ascii": ".",
        "horiz_ascii": "-",
        "vert_ascii": "|",
        "corner_dr_ascii": "+",
        "corner_dl_ascii": "+",
        "corner_ur_ascii": "+",
        "corner_ul_ascii": "+",
        "head_ascii": "o",
    }

    # (incoming_dx, incoming_dy, outgoing_dx, outgoing_dy) -> corner char name
    CORNERS = {
        (1, 0, 0, 1): "corner_dl",    # right -> down  = ╮
        (1, 0, 0, -1): "corner_ul",   # right -> up    = ╯
        (-1, 0, 0, 1): "corner_dr",   # left  -> down  = ╭
        (-1, 0, 0, -1): "corner_ur",  # left  -> up    = ╰
        (0, 1, 1, 0): "corner_ur",    # down  -> right = ╰
        (0, 1, -1, 0): "corner_ul",   # down  -> left  = ╯
        (0, -1, 1, 0): "corner_dr",   # up    -> right = ╭
        (0, -1, -1, 0): "corner_dl",  # up    -> left  = ╮
    }

    # Pre-computed age color codes
    _AGE_COLORS = ["97;1", "97", "93", "33", "2;33", "90"]
    _AGE_COLORS_DIM = ["97", "97", "93", "33", "2;33", "90"]
    _AGE_THRESHOLDS = [0.03, 0.10, 0.25, 0.50, 0.75]

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
        # Cached segment drawing data
        self._seg_cells: list[list[tuple[int, int, str]]] = []
        self._seg_corners: list[tuple[int, int, str] | None] = []
        self._head_coords: list[tuple[int, int] | None] = []
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

    def _build_segments(self) -> None:
        """Pre-compute terminal coordinates for each segment (cached on resize/rake change)."""
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

        half = self.rake_width // 2
        horiz_ch = self._get_char("horiz")
        vert_ch = self._get_char("vert")

        self._seg_cells = []
        self._seg_corners = []

        for i in range(total - 1):
            gx, gy = self._path[i]
            ngx, ngy = self._path[i + 1]
            dx, dy = self._directions[i]

            tx1 = ox + int(gx * sx)
            ty1 = oy + int(gy * sy)
            tx2 = ox + int(ngx * sx)
            ty2 = oy + int(ngy * sy)

            cells: list[tuple[int, int, str]] = []
            is_horiz = dx != 0
            ch = horiz_ch if is_horiz else vert_ch

            if is_horiz:
                step = 1 if tx2 >= tx1 else -1
                for x in range(tx1, tx2 + step, step):
                    for k in range(-half, half + 1):
                        y = ty1 + k
                        if 0 <= x < w and 0 <= y < h:
                            cells.append((x, y, ch))
            else:
                step = 1 if ty2 >= ty1 else -1
                for y in range(ty1, ty2 + step, step):
                    for k in range(-half, half + 1):
                        x = tx1 + k
                        if 0 <= x < w and 0 <= y < h:
                            cells.append((x, y, ch))

            self._seg_cells.append(cells)

            # Corner at direction change (center tine)
            corner = None
            if i > 0:
                pdx, pdy = self._directions[i - 1]
                if (pdx, pdy) != (dx, dy):
                    cname = self.CORNERS.get((pdx, pdy, dx, dy))
                    if cname and 0 <= tx1 < w and 0 <= ty1 < h:
                        corner = (tx1, ty1, self._get_char(cname))
            self._seg_corners.append(corner)

        # Head positions
        self._head_coords = []
        head_ch = self._get_char("head")
        for i in range(total):
            hgx, hgy = self._path[i]
            htx = ox + int(hgx * sx)
            hty = oy + int(hgy * sy)
            if 0 <= htx < w and 0 <= hty < h:
                self._head_coords.append((htx, hty, head_ch))
            else:
                self._head_coords.append(None)

        sand_dot = self._get_char("sand")
        self._sand_rows = []
        self._sand_colors = []
        for y in range(h):
            row_ratio = y / max(1, h - 1)
            band = 0.5 + 0.5 * math.sin(row_ratio * math.pi * 3.0 - 0.4)
            freq = 0.085 + 0.025 * math.cos(row_ratio * math.pi * 2.0)
            threshold = 0.968 + 0.012 * (1.0 - band)
            sand_chars = []
            for x in range(w):
                ripple = 0.5 + 0.5 * math.sin(x * freq + y * 0.55)
                drift = 0.5 + 0.5 * math.sin(x * (freq * 0.43) - y * 0.28)
                if ripple * 0.72 + drift * 0.28 > threshold:
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

    def render_frame(self) -> str:
        if self._built_level != self.level:
            self._build_path()

        w, h = self.width, self.height
        total = len(self._path)

        # Rebuild segment cache if dimensions/settings changed
        key = (w, h, self.rake_width, self.level, self.ascii_mode, self.brightness)
        if self._cache_key != key:
            self._build_segments()

        # Cycle: reveal -> contemplate -> dissolve -> rest
        rate = max(0.35, total / 280.0)
        t_reveal = total / rate
        t_pause = 72.0
        t_fade = 56.0
        t_rest = 18.0
        cycle = t_reveal + t_pause + t_fade + t_rest

        t = self.frame % cycle
        if t < t_reveal:
            revealed = min(total, int(t * rate))
            fade = 0.0
        elif t < t_reveal + t_pause:
            revealed = total
            fade = 0.0
        elif t < t_reveal + t_pause + t_fade:
            revealed = total
            fade = (t - t_reveal - t_pause) / t_fade
        else:
            revealed = 0
            fade = 1.0

        # Grid: None = sand, (char, color_str) = groove
        grid: list[list] = [[None] * w for _ in range(h)]

        seg_count = min(revealed, total - 1)
        inv_age_denom = 1.0 / max(1, total * 0.45)
        seg_cells = self._seg_cells
        seg_corners = self._seg_corners

        for i in range(seg_count):
            age = (seg_count - i) * inv_age_denom + fade
            color = f"\033[{self._age_color_code(age)}m"

            for x, y, ch in seg_cells[i]:
                grid[y][x] = (ch, color)

            corner = seg_corners[i]
            if corner is not None:
                cx, cy, cch = corner
                grid[cy][cx] = (cch, color)

        # Rake head
        if 0 < revealed <= total and fade == 0.0:
            hc = self._head_coords[revealed - 1]
            if hc is not None:
                hx, hy, hch = hc
                grid[hy][hx] = (hch, "\033[97m")

        # Build output with color batching
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
