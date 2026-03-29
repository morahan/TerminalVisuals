import math

from src.base import BaseVisualizer


class WaveVisualizer(BaseVisualizer):
    CHARS = {
        "wave": "~~",
        "wave_ascii": "~=",
        "foam": "^^",
        "foam_ascii": "^",
        "deep": "  ",
    }

    COLORS = {
        "deep": "\033[36m",
        "mid": "\033[96m",
        "foam": "\033[97m",
        "bright": "\033[97;1m",
    }

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
        center = self.size // 2
        max_y = self.size - 1

        for y in range(self.size):
            line = ""
            for x in range(self.size):
                char = " "
                color = ""

                for wave_idx in range(self.wave_count):
                    phase_offset = wave_idx * 0.8
                    wave_y = center + wave_idx * 2

                    amplitude = 2 + wave_idx * 0.5
                    frequency = 0.3 + wave_idx * 0.1

                    wave_pos = math.sin(
                        (x - center) * frequency + self.frame * 0.15 + phase_offset
                    ) * amplitude

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

                if char == " ":
                    char = self._get_char("deep")
                    color = self._color("36")

                line += f"{color}{char}{self.ANSI_RESET}" if color else char

            lines.append(line)

        return "\n".join(lines) + f"\n\033[{self.size + 1};1H"
