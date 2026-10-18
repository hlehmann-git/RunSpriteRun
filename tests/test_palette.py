from PIL import Image

from src.core import history, palette
from src.core.colour import level_to_8bit
from src.core.project import Frame, Group, Project
from src.core.systems import SYSTEMS, get_system


def proj(system="Atari ST"):
    a, b, c = (level_to_8bit(1, 3), 0, 0), (0, level_to_8bit(2, 3), 0), (0, 0, level_to_8bit(3, 3))
    im1 = Image.new("RGB", (4, 4), a)
    im1.putpixel((0, 0), b)
    im2 = Image.new("RGB", (4, 4), c)
    return Project("P", get_system(system), 4, 4, transparent=a, frames=[Frame("f1", im1), Frame("f2", im2)]), a, b, c


def test_replace_everywhere_and_transparent_follows():
    p, a, b, c = proj()
    new = (level_to_8bit(7, 3), level_to_8bit(7, 3), 0)
    old_images = [f.image for f in p.frames]
    palette.replace_colour(p, a, new)
    assert p.frames[0].image.getpixel((1, 1)) == new and p.frames[0].image.getpixel((0, 0)) == b
    assert p.transparent == new                                # the slot stays transparent
    assert p.frames[0].image is not old_images[0]              # new object: undo keeps the old one
    assert old_images[0].getpixel((1, 1)) == a


def test_replace_snaps_to_system():
    p, a, b, c = proj()
    palette.replace_colour(p, b, (10, 200, 30))
    assert p.frames[0].image.getpixel((0, 0)) == (0, level_to_8bit(5, 3), level_to_8bit(1, 3))


def test_merge_frees_a_slot():
    p, a, b, c = proj()
    assert len(p.palette()) == 3
    assert palette.is_duplicate(p, 1, c)
    palette.replace_colour(p, b, c)
    assert len(p.palette()) == 2


def test_unused_transparent_replace():
    p, a, b, c = proj()
    p.transparent = (255, 255, 255)
    palette.replace_colour(p, (255, 255, 255), (0, 0, 0))
    assert p.transparent == (0, 0, 0)


def test_square_geometry_matches_prd():
    for s in SYSTEMS:
        if s.is_fixed:
            continue                                            # fixed-palette systems have no colour square
        img = palette.square_image(s)
        assert img.size == (128, 128)
        assert img.getpixel((50, 70)) == palette.colour_at(s, 50, 70)
    st = get_system("Atari ST")                                 # 8 tiles of 8 x 8 blocks, 4 x 2 tiles
    assert palette.colour_at(st, 0, 0) == (0, 0, 0)
    assert palette.colour_at(st, 31, 0) == (255, 0, 0) and palette.colour_at(st, 31, 63)[1] == 255
    assert palette.colour_at(st, 32, 0)[2] == level_to_8bit(1, 3)       # next tile: blue level 1
    assert palette.colour_at(st, 0, 64)[2] == level_to_8bit(4, 3)       # second tile row: blue level 4
    assert palette.colour_at(get_system("Amiga"), 127, 127) == (255, 255, 255)
    assert palette.colour_at(get_system("Sega Master System"), 127, 127) == (255, 255, 255)
    assert palette.colour_at(get_system("Sega Master System"), 64, 0)[2] == level_to_8bit(1, 2)


def test_marker_round_trip():
    for s in SYSTEMS:
        if s.is_fixed:
            continue
        c = palette.colour_at(s, 77, 33)
        x, y, w, h = palette.marker_rect(s, c, (77, 33))
        assert palette.colour_at(s, x, y) == c
        assert x <= 77 < x + w and y <= 33 < y + h


def test_history_snapshot_restore_and_limit():
    p, a, b, c = proj()
    h = history.History()
    s0 = history.take(p)
    p.frames[0].label = "x"
    p.groups.append(Group("G", 0, 1))
    assert not s0.same_as(history.take(p))
    h.push(s0)
    cur = history.take(p)
    history.restore(p, h.undo(cur))
    assert p.frames[0].label == "f1" and p.groups == []
    history.restore(p, h.redo(history.take(p)))
    assert p.frames[0].label == "x" and len(p.groups) == 1
    for i in range(60):
        h.push(history.take(p))
    assert len(h._undo) == history.LIMIT
