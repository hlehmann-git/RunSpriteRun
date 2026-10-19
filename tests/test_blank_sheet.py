import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from src.app import blank_sheet_dialog as bsd
from src.app.main_window import MainWindow
from src.core import blank_sheet as bs
from src.core.systems import SYSTEMS, get_system
from src.io import blank_file

ST = get_system("Atari ST")
GREEN, WHITE = (0, 255, 0), (255, 0, 255)      # (WHITE is the old name: the default fill is now magenta)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_sheet_size_and_grid_lines():
    img = bs.build(ST, 32, 32, 10, 4)
    assert img.size == (640, 195) == bs.sheet_size(32, 32, 10, 4)
    assert img.mode == "RGB"
    for c in range(11):                                   # vertical lines every 33 pixels
        assert img.getpixel((c * 33, 100)) == GREEN
    for r in range(5):                                    # horizontal lines every 33 pixels
        assert img.getpixel((10, bs.BAR_H + r * 33)) == GREEN
    assert img.getpixel((1, bs.BAR_H + 1)) == WHITE and img.getpixel((32, bs.BAR_H + 32)) == WHITE
    assert img.getpixel((33, bs.BAR_H + 5)) == GREEN       # the line between two boxes is one pixel wide
    assert img.getpixel((34, bs.BAR_H + 5)) == WHITE
    assert img.getpixel((635, 120)) == bs.BG               # space beside the boxes


def test_each_box_is_exactly_the_sprite_size():
    img = bs.build(get_system("Amiga"), 16, 24, 8, 2, box=(1, 2, 3), fill=(9, 9, 9))
    inside = sum(1 for x in range(img.width) for y in range(bs.BAR_H, img.height) if img.getpixel((x, y)) == (9, 9, 9))
    assert inside == 8 * 2 * 16 * 24
    assert img.size == (max(640, 8 * 17 + 1), bs.BAR_H + 2 * 25 + 1)


def test_wide_sheets_are_not_widened_and_text_bar_is_clear_of_the_boxes():
    img = bs.build(ST, 64, 64, 31, 1)
    assert img.width == 31 * 65 + 1 == 2016
    assert any(img.getpixel((x, y)) == bs.TEXT or sum(img.getpixel((x, y))) < 200
               for x in range(0, 200) for y in range(0, bs.BAR_H))          # there is text in the bar
    assert all(img.getpixel((x, bs.BAR_H - 1)) == bs.BG for x in range(img.width))


def test_text_lines_use_the_system_data():
    lines = bs.text_lines(ST, 32, 32, 10, 4, GREEN, WHITE)
    assert len(lines) == 5
    assert "Atari ST" in lines[0] and "3 bits per channel" in lines[1] and "512" in lines[1]
    assert "16 colours" in lines[2] and "32 x 32 pixels, 10 per row, 4 rows (40 sprites)" in lines[3]
    assert "#00FF00" in lines[4] and "#FF00FF" in lines[4]
    assert "4,096" in bs.text_lines(get_system("Amiga"), 8, 8, 1, 1, GREEN, WHITE)[1]


def test_limits_and_messages():
    assert bs.problem(32, 32, 10, 4, GREEN, WHITE) is None
    assert bs.problem(64, 64, 40, 1, GREEN, WHITE) == bs.MSG_TOO_MANY          # 40 x 65 + 1 > 2,048
    assert bs.problem(8, 8, 20, 7, GREEN, WHITE) == bs.MSG_TOO_MANY            # 140 sprites
    assert bs.problem(3, 8, 2, 2, GREEN, WHITE) == bs.MSG_TOO_MANY             # size outside 4 to 64
    assert bs.problem(8, 8, 2, 2, GREEN, GREEN) == bs.MSG_SAME_COLOUR
    assert bs.problem(8, 8, 30, 4, GREEN, WHITE) is None                       # exactly 120


def test_folder_and_file_names(tmp_path):
    names = {s.name: bs.system_folder(s) for s in SYSTEMS}
    assert sorted(names.values()) == ["Amiga", "Apple_II_DoubleHiRes", "Apple_IIgs", "Atari_ST", "Atari_STE", "Commodore_64", "Genesis_Megadrive", "Master_System", "SuperFamicom_SNES"]
    assert bs.file_name(ST, 32, 32, 10, 4) == "BlankSheet_Atari_ST_32x32_10x4.png"
    p = blank_file.write(ST, 8, 8, 4, 2, GREEN, WHITE, tmp_path)
    assert p == tmp_path / "Atari_ST" / "BlankSheet_Atari_ST_8x8_4x2.png"
    img = Image.open(p)
    assert img.mode == "RGB" and img.size == (640, bs.BAR_H + 2 * 9 + 1)


def test_menu_item_exists_and_works_with_no_project(app):
    w = MainWindow()
    assert w.act_blank_sheet.text() == "Create Blank Sprite Sheet" and w.act_blank_sheet.isEnabled()
    w.set_project_active(False)
    assert w.act_blank_sheet.isEnabled()


def test_dialog_defaults_create_replace_and_refusals(app, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(bsd.messages, "warn", lambda parent, text, detail=None: shown.append(text))
    d = bsd.BlankSheetDialog(None, base=tmp_path)
    assert d.system.currentData() == "Atari ST"
    assert (d.width_box.value(), d.height_box.value(), d.per_row.value(), d.rows.value()) == (32, 32, 10, 4)
    assert d.box_colour.colour == GREEN and d.fill_colour.colour == WHITE
    assert "640 x 195 px, 40 sprites" in d.summary.text()
    assert d.hint.text().endswith("Blank sprite sheets\\Atari_ST")
    assert d.create() is True
    target = tmp_path / "Atari_ST" / "BlankSheet_Atari_ST_32x32_10x4.png"
    assert target.is_file() and str(target) in d.result.text()
    asked = []
    monkeypatch.setattr(bsd, "confirm_replace", lambda parent, files: asked.append(files) or False)
    stamp = target.stat().st_mtime_ns
    assert d.create() is False and asked == [[target.name]] and target.stat().st_mtime_ns == stamp
    monkeypatch.setattr(bsd, "confirm_replace", lambda parent, files: True)
    assert d.create() is True
    d.fill_colour.set_colour(GREEN)
    assert d.create() is False and shown[-1] == bs.MSG_SAME_COLOUR
    d.fill_colour.set_colour(WHITE)
    d.per_row.setValue(40)
    d.width_box.setValue(64)
    assert d.create() is False and shown[-1] == bs.MSG_TOO_MANY
    d.system.setCurrentIndex(d.system.findData("Amiga"))
    assert d.hint.text().endswith("\\Amiga")


def test_hex_box_rejects_bad_text(app):
    f = bsd.ColourField(None, GREEN)
    f.hex.setText("12345")
    f._typed()
    assert f.hex.text() == "#00FF00" and f.colour == GREEN
    f.hex.setText("ff8800")
    f._typed()
    assert f.colour == (255, 136, 0) and f.hex.text() == "#FF8800"


def test_width_and_height_never_exceed_128(app):
    assert bs.problem(129, 32, 2, 2, GREEN, WHITE) == bs.MSG_TOO_MANY
    assert bs.problem(32, 129, 2, 2, GREEN, WHITE) == bs.MSG_TOO_MANY
    assert bs.problem(128, 128, 2, 2, GREEN, WHITE) is None
    d = bsd.BlankSheetDialog(None)
    for box in (d.width_box, d.height_box):
        assert box.maximum() == 128 and box.minimum() == 4
        box.setValue(200)
        assert box.value() == 128                          # typing or stepping past 128 stops at 128
