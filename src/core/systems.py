"""Target systems (PRD section 5.3 system table: the single source for system data)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class System:
    name: str
    max_colours: int      # most colours a sprite can use (incl. the transparent colour)
    bits: int             # bits per channel
    depth_label: str      # e.g. "9-bit (RGB 3:3:3)"
    total_colours: int    # colours the system can display

    @property
    def levels(self) -> int:
        return 2 ** self.bits


SYSTEMS: tuple[System, ...] = (
    System("Sega Master System", 16, 2, "6-bit (RGB 2:2:2)", 64),
    System("Sega Genesis / Mega Drive", 16, 3, "9-bit (RGB 3:3:3)", 512),
    System("Super Nintendo (SNES)", 16, 5, "15-bit (RGB 5:5:5)", 32768),
    System("Atari ST", 16, 3, "9-bit (RGB 3:3:3)", 512),
    System("Atari STE", 32, 4, "12-bit (RGB 4:4:4)", 4096),
    System("Amiga", 32, 4, "12-bit (RGB 4:4:4)", 4096),
)

_BY_NAME = {s.name: s for s in SYSTEMS}


def get_system(name: str) -> System:
    """Look a system up by its exact name; raises KeyError if unknown."""
    return _BY_NAME[name]
