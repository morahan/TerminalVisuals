import argparse

from src.app import App


def parse_args():
    parser = argparse.ArgumentParser(description="Terminal Visualizer")
    parser.add_argument(
        "--mode",
        choices=["waves", "galaxy", "spiral"],
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
        "--arms", type=int, default=2, help="Number of spiral arms (default: 2)"
    )
    galaxy_group.add_argument(
        "--no-twinkle", action="store_true", help="Disable star twinkling"
    )
    galaxy_group.add_argument(
        "--arm-gap", type=int, default=2, help="Space between spiral arms (default: 2)"
    )

    spiral_group = parser.add_argument_group("Spiral Options")
    spiral_group.add_argument(
        "--trail", type=int, default=4, help="Glow trail length (default: 4)"
    )

    return parser.parse_args()


def main():
    args = parse_args()

    app = App(
        start_mode=args.mode,
        size=args.size,
        speed=args.speed,
        brightness=args.brightness,
        ascii_mode=args.ascii,
        oneshot=args.oneshot,
        wave_count=args.wave_count,
        foam=not args.no_foam,
        arms=args.arms,
        twinkle=not args.no_twinkle,
        arm_gap=args.arm_gap,
        trail=args.trail,
    )
    app.run()


if __name__ == "__main__":
    main()
