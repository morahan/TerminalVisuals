import math
import unittest

from src.galaxy import GalaxyVisualizer


class GalaxyVisualizerTests(unittest.TestCase):
    def test_render_frame_smoke_default(self):
        vis = GalaxyVisualizer(size=24)

        frame = vis.render_frame()

        self.assertIn("\033[", frame)
        self.assertTrue(frame.endswith(f"\033[{vis.height + 1};1H"))

    def test_render_frame_smoke_ascii(self):
        vis = GalaxyVisualizer(size=24, ascii_mode=True)

        frame = vis.render_frame()

        self.assertIn("\033[", frame)
        self.assertTrue(frame.endswith(f"\033[{vis.height + 1};1H"))

    def test_primary_rotation_reverses_without_flipping_precession(self):
        vis = GalaxyVisualizer(size=24, drift=2.5)
        vis.frame = 120.0
        forward = vis._motion_state()

        vis.reverse()
        reversed_state = vis._motion_state()

        self.assertAlmostEqual(forward["primary_phase"], -reversed_state["primary_phase"])
        self.assertAlmostEqual(forward["precession_phase"], reversed_state["precession_phase"])
        self.assertAlmostEqual(forward["alpha"], reversed_state["alpha"])
        self.assertAlmostEqual(forward["beta"], reversed_state["beta"])

    def test_projected_ring_points_remain_largely_in_bounds_after_resize(self):
        vis = GalaxyVisualizer(size=24)
        vis.width = 64
        vis.height = 18
        vis._on_resize()
        vis.frame = 80.0

        state = vis._motion_state()
        major, minor, _ = vis._ring_geometry()
        cx = vis.width / 2.0
        cy = vis.height / 2.0

        in_bounds = 0
        for idx in range(160):
            theta = idx * math.tau / 160
            band = math.sin(idx * 1.618 + state["precession_phase"]) * math.pi * 0.26
            x, y, _ = vis._project_ring_point(theta, band, state, cx, cy, major, minor)
            if 0 <= x < vis.width and 0 <= y < vis.height:
                in_bounds += 1

        self.assertGreater(in_bounds, 100)


if __name__ == "__main__":
    unittest.main()
