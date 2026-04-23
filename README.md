# Freio

Retro-futuristic terminal visualizer. Waves, galaxies, zen gardens, and luminous ASCII city skylines.

## Install

```bash
pipx install -e .
```

## Usage

```bash
freio                    # auto-fits terminal, starts in waves mode
freio --mode galaxy      # start in galaxy mode
freio --mode spiral      # start in droid spiral mode
freio --mode skyline     # start in the cinematic shuffled skyline tour
freio --size 31          # fixed grid size
```

## Controls

| Key            | Action                          |
|----------------|---------------------------------|
| Spacebar       | Cycle to next visualization     |
| Left / Right   | Adjust slider 1 (shape)         |
| Up / Down      | Adjust slider 2 (feel)          |
| f              | Toggle fullscreen HUD-free mode |
| e              | Toggle enjoy/fullscreen mode    |
| Esc            | Exit fullscreen and restore HUD |
| q              | Quit                            |

Every input maps to exactly one function — no modal selection needed. A brief hint overlay appears on launch and fades after a few seconds.

## Modes & Sliders

| Mode    | Slider 1           | Slider 2              |
|---------|--------------------|-----------------------|
| Waves   | Amplitude (1-6)    | Frequency (0.1-0.8)   |
| Galaxy  | Depth (0.10-0.50)  | Drift (0.5-3.0)       |
| Spiral  | Trail (1-10)       | Growth (0.1-0.6)      |
| Skyline | City (Auto-Scene)  | Glow (1-5)            |

## Options

| Flag           | Default | Description                          |
|----------------|---------|--------------------------------------|
| `--mode`       | waves   | Starting mode: `waves`, `galaxy`, `spiral`, `dyson`, `aurora`, `ember`, `ripple`, `zen`, `skyline` |
| `--size`       | auto    | Grid size (0 = fit to terminal)      |
| `--speed`      | 5       | Animation speed (higher = faster)    |
| `--brightness` | 100     | Brightness percentage                |
| `--ascii`      | off     | Use ASCII-only characters            |
| `--oneshot`    | off     | Run once then exit                   |
| `--wave-count` | 3       | Number of wave layers (waves mode)   |
| `--no-foam`    | off     | Disable foam highlights              |
| `--depth`      | 0.22    | Galaxy halo tilt depth               |
| `--drift`      | 1.5     | Galaxy precession drift intensity    |
| `--arm-gap`    | 2       | Spiral spacing                       |
| `--trail`      | 4       | Glow trail length (spiral mode)      |
| `--skyline-city` | auto  | Skyline city: `auto` or a discovered skyline scene (`newyork`, `paris`, `london`, `tokyo`, `sydney`, `dubai`, plus future scene methods) |
| `--skyline-glow` | 3     | City accent glow plus transition intensity |

## Requirements

Python 3.10+ (no external dependencies)

## Credits

Made with love by [Exponent Ventures](https://exponentventures.com) and [Freio Labs](https://freiolabs.com).
