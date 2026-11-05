"""Rotate pixel art by 45 degree steps (v2.0.20) with RotSprite, the method Aseprite uses: the picture is enlarged 8x
with Scale2x three times (which rounds off stair-step edges instead of just making blocks bigger), turned with
nearest-pixel sampling, then shrunk back by taking the middle pixel of each 8x8 block. Every pixel of the result is a
pixel of the original, so no new colours appear and the palette limits stay safe.

Quarter turns (90, 180, 270 degrees) never go through RotSprite: they are exact, so two 45 degree clicks give the same
picture as one 90 degree turn. Angles are in degrees, clockwise. No UI code here."""
from __future__ import annotations

from PIL import Image

from .colour import Colour

STEP = 45
SCALE = 8                        # three rounds of Scale2x


def normalise(angle: int) -> int:
    return angle % 360


def _scale2x(data: bytes, w: int, h: int) -> bytes:
    """One round of Scale2x (EPX) on a one-byte-per-pixel picture: each pixel becomes 2x2, and a corner takes the
    colour of its two neighbours where they agree, which smooths diagonal steps."""
    out = bytearray(4 * w * h)
    ow = 2 * w
    last_x, last_y = w - 1, h - 1
    for y in range(h):
        row = y * w
        up = row - w if y else row
        down = row + w if y < last_y else row
        o0 = 2 * y * ow
        o1 = o0 + ow
        for x in range(w):
            p = data[row + x]
            a = data[up + x]                                  # above
            d = data[down + x]                                # below
            c = data[row + x - 1] if x else p                 # left
            b = data[row + x + 1] if x < last_x else p        # right
            ox = 2 * x
            if a != d and c != b:
                out[o0 + ox] = a if c == a else p
                out[o0 + ox + 1] = b if a == b else p
                out[o1 + ox] = c if c == d else p
                out[o1 + ox + 1] = d if b == d else p
            else:
                out[o0 + ox] = out[o0 + ox + 1] = out[o1 + ox] = out[o1 + ox + 1] = p
    return bytes(out)


def _to_indices(img: Image.Image, transparent: Colour):
    """The picture as palette numbers (the transparent colour is 0) and the colour list to turn them back."""
    colours = [tuple(transparent)]
    seen = {tuple(transparent): 0}
    raw = img.convert("RGB").tobytes()
    data = bytearray(len(raw) // 3)
    for i in range(len(data)):
        c = (raw[3 * i], raw[3 * i + 1], raw[3 * i + 2])
        n = seen.get(c)
        if n is None:
            if len(colours) == 256:
                raise ValueError("RotSprite handles up to 256 colours")
            n = seen[c] = len(colours)
            colours.append(c)
        data[i] = n
    return bytes(data), colours


def _from_indices(data: bytes, size, colours) -> Image.Image:
    flat = bytearray()
    for n in data:
        flat.extend(colours[n])
    return Image.frombytes("RGB", size, bytes(flat))


def _quarter(img: Image.Image, turns: int) -> Image.Image:
    """Exact clockwise quarter turns."""
    return {0: img, 1: img.transpose(Image.ROTATE_270), 2: img.transpose(Image.ROTATE_180),
            3: img.transpose(Image.ROTATE_90)}[turns % 4]


def _rotsprite_45(img: Image.Image, transparent: Colour) -> Image.Image:
    """Turn 45 degrees clockwise. The result is bigger (the corners stick out), with the picture centred and the new
    space transparent."""
    data, colours = _to_indices(img, transparent)
    w, h = img.size
    for _ in range(3):
        data = _scale2x(data, w, h)
        w, h = 2 * w, 2 * h
    big = Image.frombytes("L", (w, h), data).rotate(-STEP, Image.NEAREST, expand=True, fillcolor=0)
    out_w, out_h = -(-big.width // SCALE), -(-big.height // SCALE)
    bp = big.load()
    bw, bh = big.width, big.height
    half = SCALE // 2
    small = bytearray(out_w * out_h)
    for y in range(out_h):
        sy = min(y * SCALE + half, bh - 1)
        for x in range(out_w):
            small[y * out_w + x] = bp[min(x * SCALE + half, bw - 1), sy]
    return _from_indices(bytes(small), (out_w, out_h), colours)


def rotate(img: Image.Image, angle: int, transparent: Colour) -> Image.Image:
    """The picture turned `angle` degrees clockwise (a multiple of 45). Quarter turns are exact; a 45 degree part
    uses RotSprite. A picture that is all transparent comes back blank at the turned size."""
    angle = normalise(angle)
    if angle % STEP:
        raise ValueError("Only steps of 45 degrees are supported")
    turned = _quarter(img, angle // 90)
    if angle % 90 == 0:
        return turned
    return _rotsprite_45(turned, transparent)


def is_blank(img: Image.Image, transparent: Colour) -> bool:
    lo_hi = img.convert("RGB").getextrema()
    return all(lo == hi == t for (lo, hi), t in zip(lo_hi, transparent))
