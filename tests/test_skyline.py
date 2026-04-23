import random
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from src.skyline import PHASE_TIMINGS, SkylineVisualizer, city_scene


class FakeClock:
    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def set(self, value: float) -> None:
        self.now = value


class ExtendedSkylineVisualizer(SkylineVisualizer):
    @city_scene("Atlantis")
    def _draw_atlantis(self, grid, horizon, seed):
        cx = self.width // 2
        for y in range(max(1, horizon - 3), horizon + 1):
            self._paint(grid, cx, y, self._get_char("solid"), "building", 12)


class SkylineVisualizerTests(unittest.TestCase):
    @staticmethod
    def _cell_counts(canvas, from_grid, to_grid):
        from_count = 0
        to_count = 0
        glow_count = 0
        for y, row in enumerate(canvas):
            for x, cell in enumerate(row):
                if cell is None:
                    continue
                if cell == from_grid[y][x]:
                    from_count += 1
                elif cell == to_grid[y][x]:
                    to_count += 1
                elif cell[2] == "glow":
                    glow_count += 1
        return from_count, to_count, glow_count

    def test_scene_discovery_supports_subclasses(self):
        clock = FakeClock()
        vis = ExtendedSkylineVisualizer(size=20, city=0, time_source=clock, rng=random.Random(0))

        self.assertIn("atlantis", vis._city_order)
        self.assertIn("newyork", vis._city_order)
        self.assertEqual(vis.sliders[0].max_val, len(vis._city_order))

    def test_auto_mode_uses_shuffle_bag_without_repeats_in_a_cycle(self):
        clock = FakeClock()
        vis = SkylineVisualizer(size=20, city=0, time_source=clock, rng=random.Random(7))

        total_cycle = PHASE_TIMINGS["city_display"] + PHASE_TIMINGS["transition"]

        seen = []
        for step in range(len(vis._city_order)):
            clock.set(step * total_cycle)
            city_name, _, phase, _ = vis._stage()
            self.assertEqual(phase, "city_display")
            seen.append(city_name)

        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(set(seen), set(vis._city_order))

    def test_phase_boundaries_follow_real_time_schedule(self):
        clock = FakeClock()
        vis = SkylineVisualizer(size=20, city=0, time_source=clock, rng=random.Random(3))

        checkpoints = [
            (0.0, "city_display"),
            (10.0, "transition"),
            (25.0, "transition"),
            (39.9, "transition"),
            (40.0, "city_display"),
        ]

        for current_time, expected_phase in checkpoints:
            clock.set(current_time)
            _, _, phase, _ = vis._stage()
            self.assertEqual(phase, expected_phase)

    def test_pinned_city_never_advances(self):
        clock = FakeClock()
        vis = SkylineVisualizer(size=20, city=2, time_source=clock, rng=random.Random(9))

        for current_time in (0.0, 10.0, 40.0, 100.0):
            clock.set(current_time)
            city_name, next_city, phase, _ = vis._stage()
            self.assertEqual(city_name, "paris")
            self.assertIsNone(next_city)
            self.assertEqual(phase, "city_display")

    def test_london_clock_uses_injected_time(self):
        clock = FakeClock()
        london_now = datetime(2026, 4, 22, 3, 0, tzinfo=ZoneInfo("Europe/London"))
        vis = SkylineVisualizer(
            size=20,
            city=3,
            time_source=clock,
            london_time_source=lambda: london_now,
            rng=random.Random(5),
        )

        hour_point, minute_point = vis._clock_hand_points(10, 10, 2)
        self.assertEqual(hour_point, (11, 10))
        self.assertEqual(minute_point, (10, 8))

    def test_london_fog_stays_above_waterline(self):
        clock = FakeClock()
        vis = SkylineVisualizer(size=20, city=3, time_source=clock, rng=random.Random(5))
        scene = vis._scene("london")
        canvas = vis._compose_city_canvas("london", scene, clock(), "city_display", 0.0)
        horizon = scene["horizon"]

        for y in range(horizon + 1, vis.height):
            for cell in canvas[y]:
                self.assertFalse(cell is not None and cell[2] == "fog")

    def test_london_fog_does_not_overwrite_water_or_reflections(self):
        clock = FakeClock()
        vis = SkylineVisualizer(size=20, city=3, time_source=clock, rng=random.Random(5))
        scene = vis._scene("london")
        canvas = vis._compose_city_canvas("london", scene, clock(), "city_display", 0.0)
        base_grid = scene["grid"]

        for y, row in enumerate(base_grid):
            for x, base_cell in enumerate(row):
                if base_cell is None:
                    continue
                if base_cell[2] in {"water", "reflection", "reflection_window"}:
                    rendered = canvas[y][x]
                    self.assertIsNotNone(rendered)
                    self.assertNotEqual(rendered[2], "fog")

    def test_london_still_has_some_fog_above_horizon(self):
        clock = FakeClock()
        vis = SkylineVisualizer(size=20, city=3, time_source=clock, rng=random.Random(5))
        scene = vis._scene("london")
        canvas = vis._compose_city_canvas("london", scene, clock(), "city_display", 0.0)
        horizon = scene["horizon"]

        fog_cells = 0
        for y in range(0, horizon + 1):
            for cell in canvas[y]:
                if cell is not None and cell[2] == "fog":
                    fog_cells += 1

        self.assertGreater(fog_cells, 0)

    def test_transition_canvas_is_deterministic(self):
        clock = FakeClock()
        vis = SkylineVisualizer(size=20, city=0, time_source=clock, rng=random.Random(3))
        vis._stage()
        clock.set(10.0)
        city_name, next_city, phase, progress = vis._stage()

        self.assertEqual(phase, "transition")
        first = vis._transition_canvas(city_name, next_city, clock(), progress)
        second = vis._transition_canvas(city_name, next_city, clock(), progress)
        self.assertEqual(first, second)

    def test_transition_canvas_stays_source_and_destination_heavy(self):
        clock = FakeClock()
        vis = SkylineVisualizer(size=20, city=0, time_source=clock, rng=random.Random(3))
        vis._stage()
        clock.set(10.0)
        city_name, next_city, phase, _ = vis._stage()

        self.assertEqual(phase, "transition")
        transition_data = vis._transition_data
        from_grid = transition_data["from_scene"]["grid"]
        to_grid = transition_data["to_scene"]["grid"]

        early = vis._transition_canvas(city_name, next_city, clock(), 0.10)
        mid = vis._transition_canvas(city_name, next_city, clock(), 0.50)
        late = vis._transition_canvas(city_name, next_city, clock(), 0.90)

        early_from, early_to, early_glow = self._cell_counts(early, from_grid, to_grid)
        mid_from, mid_to, mid_glow = self._cell_counts(mid, from_grid, to_grid)
        late_from, late_to, late_glow = self._cell_counts(late, from_grid, to_grid)

        self.assertGreater(early_from, early_to)
        self.assertGreater(late_to, late_from)
        self.assertGreater(mid_from, 40)
        self.assertGreater(mid_to, 30)
        self.assertLess(mid_glow, mid_from + mid_to)
        self.assertLess(early_glow, early_from + early_to)
        self.assertLess(late_glow, late_from + late_to)


if __name__ == "__main__":
    unittest.main()
