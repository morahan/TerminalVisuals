import math

from src.base import BaseVisualizer, Slider


class WaveVisualizer(BaseVisualizer):
    CHARS = {
        "wave": "~~",
        "wave_ascii": "~=",
        "foam": "^^",
        "foam_ascii": "^",
        "deep": "  ",
        "water_near": "▓▓",
        "water_near_ascii": "::",
        "water_mid": "▒▒",
        "water_mid_ascii": "--",
        "water_deep": "░░",
        "water_deep_ascii": "..",
    }

    sliders = [
        Slider(name="Amplitude", attr="amplitude", min_val=1.0, max_val=6.0, step=0.5),
        Slider(name="Frequency", attr="frequency", min_val=0.1, max_val=0.8, step=0.05, fmt=".2f"),
    ]

    def __init__(
        self,
        size: int = 25,
        speed: int = 5,
        brightness: int = 100,
        ascii_mode: bool = False,
        oneshot: bool = False,
        wave_count: int = 3,
        foam: bool = True,
    ):
        super().__init__(size, speed, brightness, ascii_mode, oneshot)
        self.wave_count = wave_count
        self.foam = foam
        self.amplitude = 3.0
        self.frequency = 0.3

    def _get_char(self, name: str) -> str:
        if self.ascii_mode and name in self.CHARS:
            key = f"{name}_ascii"
            return self.CHARS.get(key, self.CHARS[name])
        return self.CHARS.get(name, " ")

    def _color(self, code: str) -> str:
        if self.brightness < 100:
            code = code.replace("97", "37").replace("96", "36")
        return f"\033[{code}m"

    def render_frame(self) -> str:
        lines = []
        center_x = self.width // 4  # each cell is 2 chars wide
        center_y = self.height // 2
        x_cells = self.width // 2

        for y in range(self.height):
            line = ""
            for x in range(x_cells):
                char = " "
                color = ""
                min_depth = float('inf')

                for wave_idx in range(self.wave_count):
                    phase_offset = wave_idx * 0.8
                    wave_y = center_y + wave_idx * 2

                    amp = self.amplitude + wave_idx * 0.5
                    freq = self.frequency + wave_idx * 0.1

                    wave_pos = math.sin(
                        (x - center_x) * freq + self.frame * 0.15 + phase_offset
                    ) * amp

                    crest_y = wave_y + wave_pos
                    foam_y = crest_y - 0.5

                    dist_to_crest = abs(y - crest_y)
                    dist_to_foam = abs(y - foam_y)

                    if dist_to_crest < 0.8:
                        if dist_to_foam < 0.5 and self.foam:
                            char = self._get_char("foam")
                            color = self._color("97")
                        else:
                            char = self._get_char("wave")
                            color = self._color("96")
                    elif dist_to_crest < 1.5:
                        char = self._get_char("wave")
                        color = self._color("36")

                    # Track depth below any wave surface
                    depth = y - crest_y
                    if depth > 0:
                        min_depth = min(min_depth, depth)

                if char == " ":
                    if min_depth < float('inf'):
                        # Below a wave surface — shade by depth
                        if min_depth < 2:
                            char = self._get_char("water_near")
                            color = self._color("36")
                        elif min_depth < 5:
                            char = self._get_char("water_mid")
                            color = self._color("2;36")
                        else:
                            char = self._get_char("water_deep")
                            color = self._color("2;34")
                    else:
                        char = self._get_char("deep")
                        color = ""

                line += f"{color}{char}{self.ANSI_RESET}" if color else char

            lines.append(line)

        return "\n".join(lines) + f"\n\033[{self.height + 1};1H"
