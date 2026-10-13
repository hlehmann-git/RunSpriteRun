"""The three layers of a frame (V2.0): ForeGround on top, Core in the middle, BackGround at the bottom.
Each layer is an RGB image; a pixel of the project's transparent colour is empty and shows the layer below.
Frame.image is always the flattened picture, so everything outside the editor keeps working on one image."""
from __future__ import annotations

from PIL import Image, ImageChops

from .colour import Colour

LAYER_NAMES = ("ForeGround", "Core", "BackGround")      # top to bottom
FG, CORE, BG = 0, 1, 2


def blank(size: tuple[int, int], transparent: Colour) -> Image.Image:
    return Image.new("RGB", size, tuple(transparent))


def opaque_mask(img: Image.Image, transparent: Colour) -> Image.Image:
    """'L' image: 255 where the pixel is NOT the transparent colour."""
    r, g, b = img.split()
    same = ImageChops.darker(
        ImageChops.darker(r.point(lambda v: 255 if v == transparent[0] else 0),
                          g.point(lambda v: 255 if v == transparent[1] else 0)),
        b.point(lambda v: 255 if v == transparent[2] else 0))
    return ImageChops.invert(same)


def flatten(layers, transparent: Colour, visible=(True, True, True)) -> Image.Image:
    """Stack the layers bottom to top; only visible ones are used. Empty pixels stay transparent."""
    out = blank(layers[CORE].size, transparent)
    for i in (BG, CORE, FG):
        if visible[i]:
            out.paste(layers[i], mask=opaque_mask(layers[i], transparent))
    return out


def layers_of(frame, transparent: Colour):
    """The three layer images of a frame. A frame that was never edited has everything on Core."""
    if frame.layers is not None:
        return frame.layers
    empty = blank(frame.image.size, transparent)
    return (empty, frame.image, empty)


def set_layers(frame, layers, transparent: Colour) -> None:
    frame.layers = tuple(layers)
    frame.image = flatten(frame.layers, transparent)


def refresh(frame, transparent: Colour) -> None:
    """Recompute the flat picture of a frame that has layers (after the transparent colour changed)."""
    if frame.layers is not None:
        frame.image = flatten(frame.layers, transparent)


def colours_of(img: Image.Image) -> set:
    got = img.getcolors(img.width * img.height)
    return {c for _, c in got}
