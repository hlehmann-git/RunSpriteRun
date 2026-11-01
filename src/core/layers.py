"""The five layers of a frame (V2.0): ForeGround 2 and 1 on top, Core in the middle, BackGround 1 and 2 beneath.
Each layer is an RGB image; a pixel of the project's transparent colour is empty and shows the layer below.
Frame.image is always the flattened picture, so everything outside the editor keeps working on one image."""
from __future__ import annotations

from PIL import Image, ImageChops

from .colour import Colour

LAYER_NAMES = ("ForeGround 2", "ForeGround 1", "Core", "BackGround 1", "BackGround 2")    # top to bottom
COUNT = len(LAYER_NAMES)
FG, CORE, BG = 1, 2, 3            # where a three-layer project's ForeGround, Core and BackGround now live
TOP_DOWN = tuple(range(COUNT))                     # 0 is the top layer
BOTTOM_UP = tuple(reversed(TOP_DOWN))              # painting order: the bottom layer first


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


def flatten(layers, transparent: Colour, visible=(True,) * COUNT) -> Image.Image:
    """Stack the layers bottom to top; only visible ones are used. Empty pixels stay transparent."""
    out = blank(layers[CORE].size, transparent)
    for i in BOTTOM_UP:
        if visible[i]:
            out.paste(layers[i], mask=opaque_mask(layers[i], transparent))
    return out


def flatten_subset(images: dict, size: tuple[int, int], transparent: Colour) -> Image.Image:
    """Like flatten(), but for a {layer index: image} dict that may not have every layer (what Copy/Cut
    took from the layers that were ticked at the time). Missing layers stay transparent."""
    out = blank(size, transparent)
    for i in BOTTOM_UP:
        im = images.get(i)
        if im is not None:
            out.paste(im, mask=opaque_mask(im, transparent))
    return out


def layers_of(frame, transparent: Colour):
    """The layer images of a frame. A frame that was never edited has everything on Core."""
    if frame.layers is not None:
        return frame.layers
    empty = blank(frame.image.size, transparent)
    return tuple(frame.image if i == CORE else empty.copy() for i in TOP_DOWN)


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


def grown_layers(old, transparent: Colour):
    """A three-layer frame read from an older project file, as five layers: its ForeGround, Core and BackGround
    keep their pictures as ForeGround 1, Core and BackGround 1, and the two outer layers start empty."""
    empty = blank(old[1].size, transparent)
    return (empty.copy(), old[0], old[1], old[2], empty.copy())
