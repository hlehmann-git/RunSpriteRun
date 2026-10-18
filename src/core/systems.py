"""Target systems (PRD section 5.3 system table: the single source for system data)."""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from .colour import Colour, is_valid_colour, snap_colour


@dataclass(frozen=True)
class System:
    name: str
    max_colours: int      # most colours a sprite can use (incl. the transparent colour)
    bits: int             # bits per channel
    depth_label: str      # e.g. "9-bit (RGB 3:3:3)"
    total_colours: int    # colours the system can display
    fixed: tuple = ()     # fixed-palette systems (C64, Apple II): the only colours there are; empty = any RGB level
    default_transparent: Colour | None = None   # fixed-palette systems: the transparent colour a new project starts with

    @property
    def levels(self) -> int:
        return 2 ** self.bits

    @property
    def is_fixed(self) -> bool:
        return bool(self.fixed)

    def snap(self, colour: Colour) -> Colour:
        """The nearest colour the system can show: on the RGB grid, or the nearest colour of a fixed palette."""
        if not self.fixed:
            return snap_colour(colour, self.bits)
        colour = tuple(colour)
        if colour in self.fixed:
            return colour
        return min(self.fixed, key=lambda c: (c[0] - colour[0]) ** 2 + (c[1] - colour[1]) ** 2 + (c[2] - colour[2]) ** 2)

    def valid(self, colour: Colour) -> bool:
        return self.snap(colour) == tuple(colour) if self.fixed else is_valid_colour(colour, self.bits)

    def snap_image(self, img: Image.Image) -> Image.Image:
        """The image with every colour snapped (an RGB image comes back; the same image if nothing changes)."""
        found = img.getcolors(img.width * img.height) or []
        mapping = {c: self.snap(c) for _, c in found}
        if all(k == v for k, v in mapping.items()):
            return img
        data = img.tobytes()
        out = bytearray(len(data))
        cache = {k: bytes(v) for k, v in mapping.items()}
        for i in range(0, len(data), 3):
            out[i:i + 3] = cache[(data[i], data[i + 1], data[i + 2])]
        return Image.frombytes("RGB", img.size, bytes(out))


def _hex(*values: str) -> tuple:
    return tuple((int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)) for v in values)


# Commodore 64: the 16 colours of the VIC-II chip, in the widely used "Pepto" values.
C64_COLOURS = _hex("000000", "FFFFFF", "68372B", "70A4B2", "6F3D86", "588D43", "352879", "B8C76F",
                   "6F4F25", "433900", "9A6759", "444444", "6C6C6C", "9AD284", "6C5EB5", "959595")
# Apple II (low-res and double hi-res): the 16 colours, in the Apple IIgs values.
APPLE2_COLOURS = _hex("000000", "DD0033", "000099", "DD22DD", "007722", "555555", "2222FF", "66AAFF",
                      "885500", "FF6600", "AAAAAA", "FF9988", "11DD00", "FFFF00", "44FF99", "FFFFFF")

SYSTEMS: tuple[System, ...] = (
    System("Sega Master System", 16, 2, "6-bit (RGB 2:2:2)", 64),
    System("Sega Genesis / Mega Drive", 16, 3, "9-bit (RGB 3:3:3)", 512),
    System("Super Nintendo (SNES)", 16, 5, "15-bit (RGB 5:5:5)", 32768),
    System("Atari ST", 16, 3, "9-bit (RGB 3:3:3)", 512),
    System("Atari STE", 32, 4, "12-bit (RGB 4:4:4)", 4096),
    System("Amiga", 32, 4, "12-bit (RGB 4:4:4)", 4096),
    System("Commodore 64", 16, 8, "16 fixed colours", 16, C64_COLOURS, C64_COLOURS[14]),                 # light blue: rarely needed
    System("Apple II (Double Hi-Res)", 16, 8, "16 fixed colours", 16, APPLE2_COLOURS, APPLE2_COLOURS[2]),   # dark blue: rarely needed
)

_BY_NAME = {s.name: s for s in SYSTEMS}


def get_system(name: str) -> System:
    """Look a system up by its exact name; raises KeyError if unknown."""
    return _BY_NAME[name]
