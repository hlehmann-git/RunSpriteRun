"""Project model (section 6.2). No UI code here."""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Literal

from PIL import Image

from .colour import Colour
from .rules import DEFAULT_FPS
from .systems import System


@dataclass
class Rule:
    """Where to go: a frame or a group (used for On Release and the start state, FR-3.10)."""
    kind: Literal["frame", "group"]
    target: str            # frame label, or group name
    loop: bool = False     # only meaningful for kind == "group"
    once: bool = False     # only meaningful for kind == "group": play the group through one time, then rest on its own On Release


@dataclass
class Group:
    name: str
    first: int             # 0-based index of the first frame
    last: int              # 0-based index of the last frame
    key: str | None = None
    on_release: Rule | None = None
    colour: Colour = (0, 0, 0)   # interface-only border colour (FR-3.11)


@dataclass
class ControlRule:
    """A Frame Group Control rule: while all of `keys` are held, play `group`. Rules are checked from the top of the
    list and the first match wins; they sit above the basic key of each group (Group.key)."""
    keys: list[str]                    # W A S D and the fire buttons that must all be held, e.g. ["W", "D", "1"]
    group: str                         # the group that plays
    once: bool = False                 # True: play through one time, then hand over; False: loop while the keys are held
    release: Rule | None = None        # when all keys are let go (or a play-once ends with nothing held): None = the group's On Release
    only_in: list[str] = field(default_factory=list)   # [] = always; otherwise the rule only fires while the frame on screen belongs to one of
                                                       # these groups (for example every group in which the character faces left)


@dataclass
class Transition:
    """When the controls are about to play group `to` while the frame on screen is in one of `from_groups` ([] = any group), play
    group `play` once first. The transition group has no key of its own; it plays only because a row names it."""
    from_groups: list[str]
    to: str
    play: str
    interruptible: bool = False        # True: a change of keys while it plays stops it at once; False: it plays through first


_uids = itertools.count(1)


@dataclass
class Frame:
    label: str
    image: Image.Image     # mode "RGB", every colour valid for the system
    copied: bool = False   # made by 'Copy into new group' and not renamed yet (shown red in the timeline)
    layers: tuple | None = None   # V2.0: (ForeGround, Core, BackGround) images; None = never edited, all on Core. `image` is the flattened result
    uid: int = field(default_factory=lambda: next(_uids))   # identifies the frame through moves and Undo


@dataclass
class Project:
    name: str
    system: System
    width: int
    height: int
    fps: int = DEFAULT_FPS
    transparent: Colour = (0, 0, 0)
    frames: list[Frame] = field(default_factory=list)
    groups: list[Group] = field(default_factory=list)
    start_state: Rule | None = None
    control_rules: list[ControlRule] = field(default_factory=list)   # Frame Group Control rules, top rule first
    transitions: list[Transition] = field(default_factory=list)       # Frame Group Control transitions
    file_path: str | None = None
    source_sheet: str | None = None   # sprite sheet this project was imported from; copied into the project folder on first Save
    written_files: list[str] = field(default_factory=list)   # files Save wrote last time (relative paths), for cleaning up
    extra_colours: list[Colour] = field(default_factory=list)   # the saved palette order, kept colours included (see palette())
    dirty: bool = True      # a new project counts as unsaved until first saved (section 5.3)

    def _used_colours(self) -> dict[Colour, None]:
        """The colours the frames use, in order of first appearance (frame order, then left to right, top to bottom)."""
        seen: dict[Colour, None] = {}
        for f in self.frames:
            for img in ((f.image,) if f.layers is None else (f.image, *f.layers)):
                data = img.tobytes()
                for c in zip(data[0::3], data[1::3], data[2::3]):
                    if c not in seen:
                        seen[c] = None
        return seen

    def colour_is_used(self, colour: Colour) -> bool:
        """True if any frame (any layer) has a pixel of this colour."""
        return tuple(colour) in self._used_colours()

    def palette(self) -> list[Colour]:
        """FR-3.13: the palette. It is a saved list (`extra_colours`) that keeps its order: a colour stays in its slot
        even when no frame uses it any more (it leaves only with Delete colour or Reduce Palette). Colours the
        frames use that are not in the list yet are added at the end in order of first appearance, and the
        transparent colour is always there. The list is brought up to date here, so it always holds the whole palette."""
        order: dict[Colour, None] = {}
        for c in self.extra_colours:
            order.setdefault(tuple(c), None)
        for c in self._used_colours():
            order.setdefault(c, None)
        order.setdefault(tuple(self.transparent), None)
        result = list(order)
        self.extra_colours = list(result)
        return result

    def colours_in_use(self) -> int:
        return len(self.palette())
