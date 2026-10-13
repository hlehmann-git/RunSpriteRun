"""Makes a set of test sprite files for trying RunSpriteRun by hand.

    python tools/make_test_sprites.py [output_folder]

valid/     26 frames of a 32 x 32 character (Idle, Right, Left, Jump) that import cleanly on the
           Sega Genesis and Atari ST (3 bits per channel, 16 colours)
problems/  files that each trigger one of the import checks (PRD FR-1.2)
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

BG = (255, 0, 255)          # magenta: the first pixel, so it becomes the transparent colour
OUT = (36, 36, 36)
SKIN = (255, 182, 109)
HAIR = (109, 36, 0)
SHIRT = (0, 146, 255)
SHIRT_D = (0, 73, 219)
PANTS = (0, 36, 182)
SHOES = (73, 36, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
SIZE = 32


def person(bob=0, left_leg=0, right_leg=0, left_arm=0, right_arm=0, jump=0, facing=1) -> Image.Image:
    """A blocky 32 x 32 character. Offsets move parts by whole pixels; facing -1 mirrors it."""
    im = Image.new("RGB", (SIZE, SIZE), BG)
    d = ImageDraw.Draw(im)
    top = 3 + bob - jump

    def box(x0, y0, x1, y1, c):
        d.rectangle([x0, y0, x1, y1], fill=c)

    box(11, top, 20, top + 8, HAIR)                          # hair
    box(12, top + 3, 19, top + 8, SKIN)                      # face
    box(14, top + 5, 15, top + 6, WHITE)                     # eyes
    box(15, top + 5, 15, top + 6, BLACK)
    box(18, top + 5, 18, top + 6, BLACK)
    body = top + 9
    box(10, body, 21, body + 9, SHIRT)                       # body
    box(10, body + 6, 21, body + 7, SHIRT_D)                 # stripe
    box(7, body + left_arm, 9, body + 6 + left_arm, SKIN)    # arms
    box(22, body + right_arm, 24, body + 6 + right_arm, SKIN)
    hips = body + 10
    box(11, hips, 20, hips + 2, PANTS)                       # hips
    box(11, hips + 3, 14, hips + 7 - left_leg, PANTS)        # legs
    box(17, hips + 3, 20, hips + 7 - right_leg, PANTS)
    box(10, hips + 8 - left_leg, 14, hips + 9 - left_leg, SHOES)   # shoes
    box(17, hips + 8 - right_leg, 21, hips + 9 - right_leg, SHOES)
    d.rectangle([10, body, 10, body + 9], fill=OUT)
    if facing < 0:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    return im


def save_valid(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    idle = [person(bob=b) for b in (0, 0, -1, -1)]
    walk = [person(left_leg=l, right_leg=r, left_arm=la, right_arm=ra)
            for l, r, la, ra in [(0, 0, 0, 0), (2, 0, 2, -1), (3, 0, 3, -2), (2, 0, 2, -1),
                                 (0, 0, 0, 0), (0, 2, -1, 2), (0, 3, -2, 3), (0, 2, -1, 2)]]
    jump = [person(jump=j, left_leg=2, right_leg=2, left_arm=-2, right_arm=-2) for j in (0, 2, 3, 3, 2, 0)]
    frames = ([("Idle", im) for im in idle] + [("Right", im) for im in walk]
              + [("Left", im.transpose(Image.FLIP_LEFT_RIGHT)) for im in walk] + [("Jump", im) for im in jump])
    counts: dict[str, int] = {}
    for name, im in frames:
        counts[name] = counts.get(name, 0) + 1
        im.save(folder / f"{name}_{counts[name]}.png")


def save_problems(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    base = person()
    base.resize((16, 16), Image.NEAREST).save(folder / "wrong_size_16x16.png")
    clear = base.convert("RGBA")
    clear.putpixel((0, 0), (255, 0, 255, 0))
    clear.save(folder / "transparent_pixels.png")
    many = Image.new("RGB", (SIZE, SIZE))
    many.putdata([((x * 8) % 256 // 36 * 36, (y * 8) % 256 // 36 * 36, 73) for y in range(SIZE) for x in range(SIZE)])
    many.save(folder / "too_many_colours.png")
    off = base.copy()
    d = ImageDraw.Draw(off)
    d.rectangle([11, 12, 20, 20], fill=(100, 160, 250))      # not valid on the 3-bit grid: snapped with a warning
    off.save(folder / "colours_off_the_grid.png")
    a, b = Image.new("P", (SIZE, SIZE), 0), Image.new("P", (SIZE, SIZE), 1)
    a.save(folder / "animated.gif", save_all=True, append_images=[b], optimize=False)
    (folder / "corrupt.png").write_bytes(b"this is not a picture")
    base.save(folder / "walk 1 (copy).png")                  # spaces and brackets become underscores in the label


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("test_sprites")
    save_valid(out / "valid")
    save_problems(out / "problems")
    print("Written to", out.resolve())


if __name__ == "__main__":
    main()
