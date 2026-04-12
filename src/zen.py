import math

from src.base import BaseVisualizer, Slider, CHAR_ASPECT


class ZenVisualizer(BaseVisualizer):
    """Zen sand garden -- a rake traces a Hilbert curve, leaving parallel grooves."""

    sliders = [
        Slider(name="Rake", attr="rake_width", min_val=1, max_val=5, step=1, fmt="d"),
        Slider(name="Detail", attr="level", min_val=2, max_val=6, step=1, fmt="d"),
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

    def _get_char(self, name: str) -> str:
        if self.ascii_mode:
            return self.CHARS.get(f"{name}_ascii", self.CHARS.get(name, " "))
        return self.CHARS.get(name, " ")

    def _color(self, code: str) -> str:
        return f"\033[{code}m"

    def _age_color(self, ratio: float) -> str:
        """ANSI color for groove age (0 = fresh, 1+ = old)."""
        dim = self.brightness < 50
        if ratio < 0.03:
            return self._color("97;1") if not dim else self._color("97")
        if ratio < 0.10:
            return self._color("97")
        if ratio < 0.25:
            return self._color("93")
        if ratio < 0.50:
            return self._color("33")
        if ratio < 0.75:
            return self._color("2;33")
        return self._color("90")

    def render_frame(self) -> str:
        if self._built_level != self.level:
            self._build_path()

        w, h = self.width, self.height
        total = len(self._path)
        n = self._curve_size

        # Aspect-corrected square, centered in terminal
        pcols = min(w, int(h / CHAR_ASPECT))
        prows = int(pcols * CHAR_ASPECT)
        pcols = min(pcols, w)
        prows = min(prows, h)
        ox = (w - pcols) // 2
        oy = (h - prows) // 2
        sx = (pcols - 1) / max(1, n - 1)
        sy = (prows - 1) / max(1, n - 1)

        # Cycle: reveal -> contemplate -> dissolve -> rest
        rate = max(0.5, total / 200.0)
        t_reveal = total / rate
        t_pause = 60.0
        t_fade = 40.0
        t_rest = 10.0
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

        half = self.rake_width // 2
        seg_count = min(revealed, total - 1)

        for i in range(seg_count):
            gx, gy = self._path[i]
            ngx, ngy = self._path[i + 1]
            dx, dy = self._directions[i]

            tx1 = ox + int(gx * sx)
            ty1 = oy + int(gy * sy)
            tx2 = ox + int(ngx * sx)
            ty2 = oy + int(ngy * sy)

            age = (seg_count - i) / max(1, total * 0.3) + fade
            color = self._age_color(age)
            is_horiz = dx != 0
            ch = self._get_char("horiz") if is_horiz else self._get_char("vert")

            # Draw groove segment with parallel rake tines
            if is_horiz:
                step = 1 if tx2 >= tx1 else -1
                for x in range(tx1, tx2 + step, step):
                    for k in range(-half, half + 1):
                        y = ty1 + k
                        if 0 <= x < w and 0 <= y < h:
                            grid[y][x] = (ch, color)
            else:
                step = 1 if ty2 >= ty1 else -1
                for y in range(ty1, ty2 + step, step):
                    for k in range(-half, half + 1):
                        x = tx1 + k
                        if 0 <= x < w and 0 <= y < h:
                            grid[y][x] = (ch, color)

            # Corner at direction change (center tine only)
            if i > 0:
                pdx, pdy = self._directions[i - 1]
                if (pdx, pdy) != (dx, dy):
                    cname = self.CORNERS.get((pdx, pdy, dx, dy))
                    if cname and 0 <= tx1 < w and 0 <= ty1 < h:
                        grid[ty1][tx1] = (self._get_char(cname), color)

        # Rake head indicator
        if 0 < revealed <= total and fade == 0.0:
            hi = revealed - 1
            hgx, hgy = self._path[hi]
            htx = ox + int(hgx * sx)
            hty = oy + int(hgy * sy)
            if 0 <= htx < w and 0 <= hty < h:
                grid[hty][htx] = (self._get_char("head"), self._color("97;1"))

        # Build output with color batching
        sand_ch = self._get_char("sand")
        sand_col = self._color("2;33") if self.brightness >= 50 else self._color("90")
        reset = self.ANSI_RESET

        lines = []
        for row in grid:
            parts = []
            prev_col = None
            for cell in row:
                if cell is None:
                    c, col = sand_ch, sand_col
                else:
                    c, col = cell
                if col != prev_col:
                    parts.append(col)
                    prev_col = col
                parts.append(c)
            parts.append(reset)
            lines.append("".join(parts))

        return "\n".join(lines) + f"\n\033[{h + 1};1H"
