import argparse

from src.app import App
from src.skyline import SkylineVisualizer


def parse_args():
    skyline_city_choices = SkylineVisualizer.city_choices()
    parser = argparse.ArgumentParser(description="Terminal Visualizer")
    parser.add_argument(
        "--mode",
        choices=["waves", "galaxy", "spiral", "dyson", "aurora", "ember", "ripple", "zen", "skyline"],
        default="waves",
        help="Starting visualization mode (default: waves)",
    )
    parser.add_argument("--size", type=int, default=0, help="Grid size (0=auto-fit terminal)")
    parser.add_argument(
        "--speed", type=int, default=5, help="Animation speed, higher is faster (default: 5)"
    )
    parser.add_argument(
        "--brightness",
        type=int,
        default=100,
        help="Brightness percentage (default: 100)",
    )
    parser.add_argument("--ascii", action="store_true", help="Use ASCII-only characters")
    parser.add_argument("--oneshot", action="store_true", help="Run once, no loop")

    wave_group = parser.add_argument_group("Wave Options")
    wave_group.add_argument(
        "--wave-count", type=int, default=3, help="Number of wave layers (default: 3)"
    )
    wave_group.add_argument(
        "--no-foam", action="store_true", help="Disable foam highlights"
    )

    galaxy_group = parser.add_argument_group("Galaxy Options")
    galaxy_group.add_argument(
        "--depth", type=float, default=0.22, help="Halo tilt depth (default: 0.22)"
    )
    galaxy_group.add_argument(
        "--drift", type=float, default=1.5, help="Precession drift intensity (default: 1.5)"
    )

    spiral_group = parser.add_argument_group("Spiral Options")
    spiral_group.add_argument(
        "--arm-gap", type=int, default=2, help="Spiral spacing (default: 2)"
    )
    spiral_group.add_argument(
        "--trail", type=int, default=4, help="Glow trail length (default: 4)"
    )

    dyson_group = parser.add_argument_group("Dyson Options")
    dyson_group.add_argument(
        "--spread", type=float, default=0.30, help="Ring tilt spread (default: 0.30)"
    )
    dyson_group.add_argument(
        "--orbit-speed", type=float, default=1.5, help="Orbital speed (default: 1.5)"
    )

    aurora_group = parser.add_argument_group("Aurora Options")
    aurora_group.add_argument(
        "--curtains", type=int, default=5, help="Number of curtain bands (default: 5)"
    )
    aurora_group.add_argument(
        "--shimmer", type=float, default=1.5, help="Wave amplitude (default: 1.5)"
    )

    ember_group = parser.add_argument_group("Ember Options")
    ember_group.add_argument(
        "--density", type=int, default=80, help="Number of particles (default: 80)"
    )
    ember_group.add_argument(
        "--warmth", type=float, default=1.5, help="Color temperature (default: 1.5)"
    )

    ripple_group = parser.add_argument_group("Ripple Options")
    ripple_group.add_argument(
        "--sources", type=int, default=2, help="Number of ripple sources (default: 2)"
    )
    ripple_group.add_argument(
        "--wavelength", type=float, default=4.0, help="Ring spacing (default: 4.0)"
    )

    zen_group = parser.add_argument_group("Zen Options")
    zen_group.add_argument(
        "--rake-width", type=int, default=3, help="Parallel rake grooves (default: 3)"
    )
    zen_group.add_argument(
        "--zen-level", type=int, default=4, help="Hilbert curve detail level (default: 4)"
    )

    skyline_group = parser.add_argument_group("Skyline Options")
    skyline_group.add_argument(
        "--skyline-city",
        choices=skyline_city_choices,
        default="auto",
        help="Pinned skyline city or auto tour (default: auto)",
    )
    skyline_group.add_argument(
        "--skyline-glow", type=int, default=3, help="Window and reflection glow (default: 3)"
    )

    return parser.parse_args()


def main():
    args = parse_args()
    skyline_city_map = SkylineVisualizer.city_choice_map()

    app = App(
        start_mode=args.mode,
        size=args.size,
        speed=args.speed,
        brightness=args.brightness,
        ascii_mode=args.ascii,
        oneshot=args.oneshot,
        wave_count=args.wave_count,
        foam=not args.no_foam,
        depth=args.depth,
        drift=args.drift,
        arm_gap=args.arm_gap,
        trail=args.trail,
        spread=args.spread,
        orbit_speed=args.orbit_speed,
        curtains=args.curtains,
        shimmer=args.shimmer,
        density=args.density,
        warmth=args.warmth,
        sources=args.sources,
        wavelength=args.wavelength,
        rake_width=args.rake_width,
        zen_level=args.zen_level,
        skyline_city=skyline_city_map[args.skyline_city],
        skyline_glow=args.skyline_glow,
    )
    app.run()


if __name__ == "__main__":
    main()
