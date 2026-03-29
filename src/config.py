from dataclasses import dataclass
from typing import Literal


@dataclass
class BaseConfig:
    size: int = 25
    speed: int = 5
    brightness: int = 100
    ascii_mode: bool = False
    oneshot: bool = False


@dataclass
class WaveConfig(BaseConfig):
    wave_count: int = 3
    foam: bool = True


@dataclass
class GalaxyConfig(BaseConfig):
    arms: int = 2
    twinkle: bool = True
    arm_gap: int = 2


@dataclass
class VisualizerConfig:
    mode: Literal["waves", "galaxy"]
    base: BaseConfig
    wave: WaveConfig | None = None
    galaxy: GalaxyConfig | None = None
