import math
import unittest

from src.galaxy import GalaxyVisualizer


class GalaxyVisualizerTests(unittest.TestCase):
    def test_galaxy_exposes_only_depth_and_drift_sliders(self):
        slider_names = [slider.name for slider in GalaxyVisualizer.sliders]
        slider_attrs = [slider.attr for slider in GalaxyVisualizer.sliders]

        self.assertEqual(slider_names, ["Depth", "Drift"])
        self.assertEqual(slider_attrs, ["depth", "drift"])

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

    def test_default_motion_is_slower_than_previous_drift_level(self):
        default = GalaxyVisualizer(size=24)
        previous_default = GalaxyVisualizer(size=24, drift=1.5)
        default.frame = 120.0
        previous_default.frame = 120.0

        self.assertEqual(default.drift, 0.75)
        self.assertLess(abs(default._rotation_amount()), abs(previous_default._rotation_amount()))

    def test_full_width_geometry_tracks_terminal_columns(self):
        vis = GalaxyVisualizer(size=24, depth=0.22)
        vis.width = 120
        vis.height = 24
        vis._on_resize()

        x_radius, y_radius = vis._screen_radii()

        self.assertGreaterEqual(x_radius * 2, vis.width * 0.95)
        self.assertLessEqual(y_radius * 2, vis.height)

    def test_depth_controls_vertical_spread(self):
        shallow = GalaxyVisualizer(size=24, depth=0.10)
        deep = GalaxyVisualizer(size=24, depth=0.50)
        for vis in (shallow, deep):
            vis.width = 80
            vis.height = 40

        _, shallow_y = shallow._screen_radii()
        _, deep_y = deep._screen_radii()

        self.assertLess(shallow_y, deep_y)

    def test_projected_spiral_points_remain_in_bounds_after_resize(self):
        vis = GalaxyVisualizer(size=24, depth=0.22)
        vis.width = 96
        vis.height = 24
        vis._on_resize()
        vis.frame = 120.0

        cx = vis.width / 2.0
        cy = vis.height / 2.0

        in_bounds = 0
        for idx in range(160):
            angle = idx * math.tau / 160
            x, y, _ = vis._galaxy_coords(angle, 1.0)
            if 0 <= cx + x < vis.width and 0 <= cy + y < vis.height:
                in_bounds += 1

        self.assertGreater(in_bounds, 150)

    def test_star_count_regenerates_for_larger_resizes(self):
        vis = GalaxyVisualizer(size=24)
        small_count = len(vis.stars)

        vis.width = 140
        vis.height = 32
        vis._on_resize()

        self.assertGreater(len(vis.stars), small_count)


if __name__ == "__main__":
    unittest.main()
