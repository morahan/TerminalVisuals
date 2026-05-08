import unittest

from src.base import BaseVisualizer, MAX_RENDER_CELLS
from src.spiral import SpiralVisualizer


class HugeTerminalProbe(BaseVisualizer):
    def _get_terminal_size(self) -> tuple[int, int]:
        return 500, 200

    def render_frame(self) -> str:
        return ""


class RenderSafetyTests(unittest.TestCase):
    def test_auto_size_caps_render_cells_for_huge_terminals(self):
        vis = HugeTerminalProbe(size=0)

        self.assertEqual(vis.width, 500)
        self.assertLessEqual(vis.width * vis.height, MAX_RENDER_CELLS)

    def test_spiral_tiny_size_does_not_create_negative_growth(self):
        vis = SpiralVisualizer(size=1, ascii_mode=True, oneshot=True)

        self.assertGreaterEqual(vis.max_radius, 1)
        self.assertGreater(vis.growth, 0)
        frame = vis.render_frame()
        self.assertIn("\033[2;1H", frame)


if __name__ == "__main__":
    unittest.main()
