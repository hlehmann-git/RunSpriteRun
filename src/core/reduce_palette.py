"""Reduce palette (Edit menu): the project is left with fewer colours. The program chooses which colours stay, and every
pixel of a removed colour becomes the nearest colour that stays. The transparent colour is fixed: it is never counted and
never removed. Only colours the project already has are kept, so the result always fits the system. No UI code here."""
from __future__ import annotations

from PIL import Image

from .colour import Colour
from . import layers as layer_rules
from .project import Project

MIN_COLOURS = 2
MSG_NOTHING = "This project has no colours that can be removed."


def _images(project: Project):
    for f in project.frames:
        yield from ((f.image,) if f.layers is None else f.layers)


def colour_counts(project: Project) -> dict[Colour, int]:
    """Colours of the project (not the transparent one) and how many pixels use each, in palette order. Colours that are
    only in the palette (added, not yet drawn) count as 0."""
    counts: dict[Colour, int] = {}
    for img in _images(project):
        data = img.tobytes()
        for c in zip(data[0::3], data[1::3], data[2::3]):
            counts[c] = counts.get(c, 0) + 1
    out = {c: counts.get(c, 0) for c in project.palette() if c != project.transparent}
    return out


def colour_count(project: Project) -> int:
    """The number of colours that can be reduced (the transparent colour is not counted)."""
    return len([c for c in project.palette() if c != project.transparent])


def can_reduce(project: Project) -> bool:
    return colour_count(project) > MIN_COLOURS


def target_range(project: Project) -> tuple[int, int]:
    """(lowest, highest) number of colours the user may ask for."""
    return MIN_COLOURS, colour_count(project) - 1


def _dist(a: Colour, b: Colour) -> int:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def choose_colours(counts: dict[Colour, int], keep: int) -> list[Colour]:
    """The `keep` colours to leave. Colours are merged two at a time: the pair that costs the picture least (few pixels
    and similar colours) goes first, and the colour with more pixels survives. A small but very different colour (an eye,
    a highlight) costs a lot to merge, so it stays. Same input, same answer."""
    groups = [(c, n) for c, n in counts.items()]        # (surviving colour, pixels)
    while len(groups) > keep:
        best = None
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                (a, na), (b, nb) = groups[i], groups[j]
                cost = (na * nb / (na + nb) if na + nb else 0) * _dist(a, b)
                if best is None or cost < best[0]:
                    best = (cost, i, j)
        _, i, j = best
        (a, na), (b, nb) = groups[i], groups[j]
        win = a if (na, -groups.index((a, na))) >= (nb, -groups.index((b, nb))) else b
        groups[i] = (win, na + nb)
        del groups[j]
    kept = {c for c, _ in groups}
    return [c for c in counts if c in kept]


def make_mapping(counts: dict[Colour, int], keep: int) -> dict[Colour, Colour]:
    """Every colour -> the colour it becomes (kept colours map to themselves)."""
    kept = choose_colours(counts, keep)
    return {c: (c if c in kept else min(kept, key=lambda k: _dist(c, k))) for c in counts}


def remap_image(img: Image.Image, mapping: dict[Colour, Colour]) -> Image.Image:
    data = img.tobytes()
    table = {c: bytes(n) for c, n in mapping.items() if c != n}
    if not table:
        return img
    out = bytearray(data)
    for i in range(0, len(data), 3):
        r = table.get((data[i], data[i + 1], data[i + 2]))
        if r is not None:
            out[i:i + 3] = r
    return Image.frombytes("RGB", img.size, bytes(out))


def reduce_project(project: Project, keep: int) -> dict[Colour, Colour]:
    """Reduce the project to `keep` colours (plus the transparent one) in place; marks it unsaved. Returns the mapping.
    Raises ValueError if `keep` is out of range."""
    lo, hi = target_range(project)
    if not lo <= keep <= hi:
        raise ValueError(MSG_NOTHING if hi < lo else f"Choose between {lo} and {hi} colours.")
    mapping = make_mapping(colour_counts(project), keep)
    for f in project.frames:
        if f.layers is not None:
            layer_rules.set_layers(f, tuple(remap_image(im, mapping) for im in f.layers), project.transparent)
        else:
            f.image = remap_image(f.image, mapping)
    kept = set(mapping.values())
    project.extra_colours = [c for c in project.extra_colours if c in kept]        # the freed places are free again
    project.dirty = True
    return mapping
