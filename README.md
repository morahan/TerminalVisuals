# Freio

Retro-futuristic terminal visualizer. Waves, galaxies, and a droid boot-sequence spiral.

## Install

```bash
pipx install -e .
```

## Usage

```bash
freio                    # auto-fits terminal, starts in waves mode
freio --mode galaxy      # start in galaxy mode
freio --mode spiral      # start in droid spiral mode
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
| Galaxy  | Arms (1-8)         | Tightness (0.1-1.0)   |
| Spiral  | Trail (1-10)       | Growth (0.1-0.6)      |

## Options

| Flag           | Default | Description                          |
|----------------|---------|--------------------------------------|
| `--mode`       | waves   | Starting mode: `waves`, `galaxy`, `spiral` |
| `--size`       | auto    | Grid size (0 = fit to terminal)      |
| `--speed`      | 5       | Animation speed (higher = faster)    |
| `--brightness` | 100     | Brightness percentage                |
| `--ascii`      | off     | Use ASCII-only characters            |
| `--oneshot`    | off     | Run once then exit                   |
| `--wave-count` | 3       | Number of wave layers (waves mode)   |
| `--no-foam`    | off     | Disable foam highlights              |
| `--arms`       | 2       | Spiral arms (galaxy mode)            |
| `--no-twinkle` | off     | Disable star twinkling               |
| `--arm-gap`    | 2       | Space between spiral arms            |
| `--trail`      | 4       | Glow trail length (spiral mode)      |

## Requirements

Python 3.10+ (no external dependencies)

## Credits

Made with love by [Exponent Ventures](https://exponentventures.com) and [Freio Labs](https://freiolabs.com).
