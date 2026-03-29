import sys
import time
from abc import ABC, abstractmethod
from typing import Callable


class BaseVisualizer(ABC):
    ANSI_CLEAR = "\033[2J"
    ANSI_HOME = "\033[H"
    ANSI_RESET = "\033[0m"

    def __init__(
        self,
        size: int = 25,
        speed: int = 5,
        brightness: int = 100,
        ascii_mode: bool = False,
        oneshot: bool = False,
    ):
        self.size = size
        self.speed = speed
        self.brightness = brightness
        self.ascii_mode = ascii_mode
        self.oneshot = oneshot
        self.frame = 0
        self.running = True

    def clear_screen(self) -> str:
        return f"{self.ANSI_CLEAR}{self.ANSI_HOME}"

    @abstractmethod
    def render_frame(self) -> str:
        pass

    def run(self) -> None:
        try:
            while self.running:
                output = self.clear_screen() + self.render_frame()
                sys.stdout.write(output)
                sys.stdout.flush()

                if self.oneshot:
                    self.running = False
                    break

                time.sleep(1.0 / self.speed)
                self.frame += 1
        except KeyboardInterrupt:
            pass
        finally:
            self._cleanup()

    def _cleanup(self) -> None:
        sys.stdout.write(f"{self.ANSI_CLEAR}{self.ANSI_HOME}{self.ANSI_RESET}")
        sys.stdout.flush()
