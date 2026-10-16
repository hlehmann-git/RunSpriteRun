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


@dataclass
class Group:
    name: str
    first: int             # 0-based index of the first frame
    last: int              # 0-based index of the last frame
    key: str | None = None
    on_release: Rule | None = None
    colour: Colour = (0, 0, 0)   # interface-only border colour (FR-3.11)


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
    file_path: str | None = None
    source_sheet: str | None = None   # sprite sheet this project was imported from; copied into the project folder on first Save
    written_files: list[str] = field(default_factory=list)   # files Save wrote last time (relative paths), for cleaning up
    extra_colours: list[Colour] = field(default_factory=list)   # V2.0: colours added with the + colour tool before they are drawn
    dirty: bool = True      # a new project counts as unsaved until first saved (section 5.3)

    def palette(self) -> list[Colour]:
        """FR-3.13: colours in order of first appearance (frame order, then left to right,
        top to bottom). The transparent colour is always kept: if no frame uses it, it goes last."""
        seen: dict[Colour, None] = {}
        for f in self.frames:
            for img in ((f.image,) if f.layers is None else (f.image, *f.layers)):
                data = img.tobytes()
                for c in zip(data[0::3], data[1::3], data[2::3]):
                    if c not in seen:
                        seen[c] = None
        for c in self.extra_colours:
            if c not in seen and c != self.transparent:
                seen[c] = None
        if self.transparent not in seen:
            seen[self.transparent] = None
        return list(seen)

    def colours_in_use(self) -> int:
        return len(self.palette())
