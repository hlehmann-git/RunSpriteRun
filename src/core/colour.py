"""Colour conversion rules (FR-1.6). Snapping each channel on its own gives the
nearest valid colour exactly, and no rounding ties are possible with these divisors."""
from __future__ import annotations

import re

Colour = tuple[int, int, int]

_HEX_RE = re.compile(r"^#?([0-9A-Fa-f]{6})$")


def level_to_8bit(level: int, bits: int) -> int:
    """value = round(level x 255 / (2^b - 1)), in integer arithmetic."""
    top = (1 << bits) - 1
    return (level * 255 * 2 + top) // (2 * top)


def to_level(value: int, bits: int) -> int:
    """level = round(value x (2^b - 1) / 255), in integer arithmetic."""
    top = (1 << bits) - 1
    return (value * top * 2 + 255) // (2 * 255)


def snap_channel(value: int, bits: int) -> int:
    return level_to_8bit(to_level(value, bits), bits)


def snap_colour(colour: Colour, bits: int) -> Colour:
    return (snap_channel(colour[0], bits), snap_channel(colour[1], bits), snap_channel(colour[2], bits))


def channel_values(bits: int) -> list[int]:
    """The 8-bit values of every level, level 0 upward."""
    return [level_to_8bit(i, bits) for i in range(1 << bits)]


def is_valid_colour(colour: Colour, bits: int) -> bool:
    return snap_colour(colour, bits) == tuple(colour)


def snap_lut(bits: int) -> list[int]:
    """256-entry lookup table mapping any 8-bit value to its snapped value."""
    return [snap_channel(v, bits) for v in range(256)]


def to_hex(colour: Colour) -> str:
    return "#{:02X}{:02X}{:02X}".format(*colour)


def parse_hex(text: str) -> Colour | None:
    """Six hex digits, with or without '#'. Returns None if the text is not valid (FR-3.13)."""
    m = _HEX_RE.match(text.strip())
    if not m:
        return None
    h = m.group(1)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
