from pathlib import Path

from PIL import Image

from src.core.factory import create_project
from src.core.importer import (MSG_GIF_ANIMATED, MSG_TRANSPARENCY, import_files, msg_frame_limit,
                               msg_too_many_colours, natural_key)
from src.core.systems import get_system
from tests.helpers import make_png

GENESIS = get_system("Sega Genesis / Mega Drive")
SMS = get_system("Atari ST")


def test_natural_order(tmp_path):
    paths = [make_png(tmp_path / n) for n in ("frame10.png", "frame2.png", "Frame1.png")]
    res = import_files(paths, GENESIS, 8, 8)
    assert [f.label for f in res.frames] == ["Frame1", "frame2", "frame10"]
    assert natural_key(Path("a2.png")) < natural_key(Path("a10.png"))


def test_frame_limit(tmp_path):
    p = make_png(tmp_path / "a.png")
    assert import_files([p] * 120, GENESIS, 8, 8).rejected is None
    res = import_files([p] * 121, GENESIS, 8, 8)
    assert res.rejected == msg_frame_limit(121) and not res.frames and not res.can_create


def test_size_blocks_create(tmp_path):
    ok = make_png(tmp_path / "a.png")
    bad = make_png(tmp_path / "b.png", size=(9, 8))
    res = import_files([ok, bad], GENESIS, 8, 8)
    assert res.size_errors == ["b.png is 9 x 8 but the project frame size is 8 x 8."]
    assert not res.can_create


def test_transparency_rejected_opaque_alpha_accepted(tmp_path):
    clear = tmp_path / "clear.png"
    Image.new("RGBA", (8, 8), (0, 0, 0, 0)).save(clear)
    solid = tmp_path / "solid.png"
    Image.new("RGBA", (8, 8), (0, 0, 0, 255)).save(solid)
    gif = tmp_path / "t.gif"
    Image.new("P", (8, 8), 0).save(gif, transparency=0)
    res = import_files([clear, solid, gif], GENESIS, 8, 8)
    assert [f.label for f in res.frames] == ["solid"]
    reasons = {s.file: s.reason for s in res.skipped}
    assert reasons["clear.png"] == MSG_TRANSPARENCY and reasons["t.gif"] == MSG_TRANSPARENCY


def test_animated_gif_and_unreadable(tmp_path):
    gif = tmp_path / "anim.gif"
    a, b = Image.new("P", (8, 8), 0), Image.new("P", (8, 8), 1)
    a.save(gif, save_all=True, append_images=[b], optimize=False)
    junk = tmp_path / "junk.png"
    junk.write_bytes(b"not an image")
    res = import_files([gif, junk], GENESIS, 8, 8)
    assert {s.file: s.reason for s in res.skipped} == {
        "anim.gif": MSG_GIF_ANIMATED, "junk.png": "junk.png could not be read."}


def test_snapping_warning_and_values(tmp_path):
    p = make_png(tmp_path / "s.png", colours=((100, 200, 10), (0, 0, 0)))
    res = import_files([p], GENESIS, 8, 8)
    assert res.frames[0].image.getpixel((0, 0)) == (109, 182, 0)
    adj = res.adjustments[0]
    assert adj.file == "s.png" and adj.count == 1 and adj.details == [((100, 200, 10), (109, 182, 0))]


def test_colour_count_limit_and_skip(tmp_path):
    many = make_png(tmp_path / "a_many.png", size=(8, 8), colours=[(i * 36 % 256, 0, 0) for i in range(8)] +
                    [(0, i * 36 % 256, 0) for i in range(1, 8)] + [(0, 0, 36)] * 2)   # 16 distinct
    extra = make_png(tmp_path / "b_extra.png", colours=((255, 255, 255),))
    res = import_files([many, extra], GENESIS, 8, 8)
    assert len(res.frames) == 1
    assert res.skipped[0].reason == msg_too_many_colours(16)


def test_snapped_colours_counted_after_snapping(tmp_path):
    # 20 distinct 8-bit colours that collapse to few valid ones on the 3-bit Atari ST
    cols = [(i * 12, 0, 0) for i in range(20)]
    p = make_png(tmp_path / "a.png", size=(5, 4), colours=cols)
    res = import_files([p], SMS, 5, 4)
    assert len(res.frames) == 1 and not res.skipped


def test_create_project_and_palette(tmp_path):
    p1 = make_png(tmp_path / "a.png", colours=((255, 0, 0), (0, 0, 0)))
    p2 = make_png(tmp_path / "b.png", colours=((0, 0, 255),))
    res = import_files([p1, p2], GENESIS, 8, 8)
    proj = create_project("Demo", GENESIS, 8, 8, res)
    assert proj.transparent == (255, 0, 0)          # first pixel of first frame
    assert proj.palette() == [(255, 0, 0), (0, 0, 0), (0, 0, 255)]
    proj.transparent = (73, 73, 73)                 # unused transparent colour is kept, last
    assert proj.palette()[-1] == (73, 73, 73)
