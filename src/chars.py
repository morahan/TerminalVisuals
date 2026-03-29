from typing import Dict


BOX_CHARS: Dict[str, str] = {
    "dot":        "●",
    "ring":       "◯",
    "block":      "█",
    "half_block": "▓",
    "light":      "░",
    "medium":     "▒",
    "arc_tl":     "╭",
    "arc_tr":     "╮",
    "arc_bl":     "╰",
    "arc_br":     "╯",
    "vert":       "│",
    "horiz":      "─",
    "cross":      "┼",
    "bright":     "◆",
    "dim":        "·",
    "spark":      "✦",
    "glow":       "◈",
}

ASCII_CHARS: Dict[str, str] = {
    "dot":        "o",
    "ring":       "O",
    "block":      "#",
    "half_block": "%",
    "light":      ".",
    "medium":     ":",
    "arc_tl":     "+",
    "arc_tr":     "+",
    "arc_bl":     "+",
    "arc_br":     "+",
    "vert":       "|",
    "horiz":      "-",
    "cross":      "+",
    "bright":     "*",
    "dim":        ".",
    "spark":      "*",
    "glow":       "@",
}

# Spiral trail characters ordered from brightest to dimmest
TRAIL_CHARS_BOX = ["█", "▓", "▒", "░", "·", " "]
TRAIL_CHARS_ASCII = ["#", "%", ":", ".", " ", " "]


def get_charset(ascii_only: bool) -> Dict[str, str]:
    return ASCII_CHARS if ascii_only else BOX_CHARS


def get_trail_chars(ascii_only: bool) -> list[str]:
    return TRAIL_CHARS_ASCII if ascii_only else TRAIL_CHARS_BOX
