"""Fixed-palette systems (Commodore 64, Apple II): 16 colours that cannot be changed."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from src.app.main_window import MainWindow
from src.app.info_dialogs import information_rows
from src.core import editing, palette
from src.core import blank_sheet as bs
from src.core.factory import create_project
from src.core.importer import ImportedFrame, ImportResult, import_files
from src.core.project import Frame, Project
from src.core.sheet_import import import_sheet, SheetGrid
from src.core.systems import APPLE2_COLOURS, C64_COLOURS, SYSTEMS, get_system
from src.io.project_file import ProjectFileError, open_project, save_project

C64 = get_system("Commodore 64")
APPLE = get_system("Apple II (Double Hi-Res)")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def blank_project(system=C64, w=8, h=8):
    t = system.default_transparent
    result = ImportResult(frames=[ImportedFrame("Frame", Image.new("RGB", (w, h), t))])
    p = create_project("P", system, w, h, result)
    p.transparent = t
    return p


def test_the_two_systems_have_sixteen_distinct_colours():
    for s, colours in ((C64, C64_COLOURS), (APPLE, APPLE2_COLOURS)):
        assert s.is_fixed and s.fixed == colours and len(set(colours)) == 16
        assert s.max_colours == 16 and s.total_colours == 16
        assert s.default_transparent in colours
    assert C64.default_transparent == (0x6C, 0x5E, 0xB5)           # light blue, rarely needed
    assert APPLE.default_transparent == (0, 0, 0x99)               # dark blue
    assert [s.name for s in SYSTEMS][-2:] == ["Commodore 64", "Apple II (Double Hi-Res)"]
    assert not get_system("Amiga").is_fixed


def test_snap_picks_the_nearest_fixed_colour():
    assert C64.snap((0, 0, 0)) == (0, 0, 0)
    assert C64.snap((250, 250, 250)) == (255, 255, 255)
    assert C64.snap((5, 5, 5)) == (0, 0, 0)
    assert C64.valid((255, 255, 255)) and not C64.valid((250, 250, 250))
    for c in C64_COLOURS:
        assert C64.snap(c) == c
    assert get_system("Amiga").snap((255, 0, 255)) == (255, 0, 255)       # the grid systems are unchanged
    assert get_system("Amiga").snap((250, 3, 7)) == (255, 0, 0)


def test_snap_image_changes_only_what_it_must():
    img = Image.new("RGB", (4, 1), (255, 255, 255))
    assert C64.snap_image(img) is img
    img.putpixel((1, 0), (250, 250, 250))
    out = C64.snap_image(img)
    assert out is not img and set(out.getdata()) == {(255, 255, 255)}


def test_new_project_has_every_colour_in_the_palette():
    p = blank_project()
    pal = p.palette()
    assert len(pal) == 16 and set(pal) == set(C64_COLOURS)
    assert pal[0] == C64.default_transparent                          # the transparent colour is the first one
    assert p.colours_in_use() == 16


def test_colours_cannot_be_added_or_replaced():
    p = blank_project()
    assert not editing.can_add_colour(p, (1, 2, 3))
    assert not editing.add_colour(p, (1, 2, 3))


def test_import_snaps_to_the_fixed_colours(tmp_path):
    img = Image.new("RGB", (4, 4), (250, 250, 250))
    img.putpixel((0, 0), (3, 3, 3))
    f = tmp_path / "a.png"
    img.save(f)
    res = import_files([f], C64, 4, 4)
    assert res.can_create and not res.skipped
    assert set(res.frames[0].image.getdata()) == {(255, 255, 255), (0, 0, 0)}
    assert res.adjustments and res.adjustments[0].count == 2
    assert {adj for _, adj in res.adjustments[0].details} == {(255, 255, 255), (0, 0, 0)}


def test_import_with_too_many_colours_for_the_system_is_still_possible_when_they_snap_together(tmp_path):
    img = Image.new("RGB", (6, 6))
    for i in range(36):
        img.putpixel((i % 6, i // 6), (i * 7, i * 7, i * 7))            # 36 greys: they snap to the few greys of the palette
    f = tmp_path / "g.png"
    img.save(f)
    res = import_files([f], APPLE, 6, 6)
    assert res.can_create and len(set(res.frames[0].image.getdata())) <= 16


def test_sheet_import_snaps_and_uses_the_nearest_colour_as_transparent():
    sheet = Image.new("RGB", (10, 5), (255, 0, 255))
    for x in range(1, 4):
        for y in range(1, 4):
            sheet.putpixel((x, y), (252, 252, 252))
    grid = SheetGrid(width=3, height=3, boxes=[(1, 1), (6, 1)])
    res = import_sheet(sheet, "sh", grid, (255, 0, 255), C64)
    assert res.rejected is None and len(res.frames) == 1
    assert set(res.frames[0].image.getdata()) == {(255, 255, 255)}


def test_save_and_open_round_trip(tmp_path):
    p = blank_project()
    p.frames[0].image.putpixel((1, 1), (0, 0, 0))
    (tmp_path / "P").mkdir()
    path = tmp_path / "P" / "P.rsr"
    save_project(p, path)
    q = open_project(path)
    assert q.system is C64 and set(q.palette()) == set(C64_COLOURS)
    assert q.frames[0].image.getpixel((1, 1)) == (0, 0, 0)


def test_open_refuses_a_colour_that_is_not_in_the_palette(tmp_path):
    p = blank_project()
    p.frames[0].image.putpixel((1, 1), (1, 2, 3))
    (tmp_path / "P").mkdir()
    path = tmp_path / "P" / "P.rsr"
    save_project(p, path)
    with pytest.raises(ProjectFileError):
        open_project(path)


def test_texts_for_fixed_systems():
    rows = dict(information_rows(blank_project()))
    assert rows["Colour depth"] == "16 fixed colours" and "fixed" in rows["Bits per channel"]
    lines = bs.text_lines(C64, 8, 8, 1, 1, (0, 255, 0), (255, 255, 255))
    assert "fixed colours" in lines[1] and "bits per channel" not in lines[1]


def test_colour_editor_is_locked(app):
    win = MainWindow()
    win.show()
    win.set_project(blank_project())
    ed = win.panels["Colour editor"]
    assert ed.locked and not ed.square.isVisible() and not ed.hex.isEnabled()
    assert not any(s.isEnabled() for s in ed.sliders)
    ed._set_colour((0, 0, 0), arm=True)
    assert not ed.armed                                       # nothing can be overwritten
    assert win.controller.replace_colour(0, (0, 0, 0)) is False
    win.set_project(Project("P", get_system("Amiga"), 4, 4, frames=[Frame("f_001", Image.new("RGB", (4, 4)))]))
    assert not ed.locked and ed.hex.isEnabled()
