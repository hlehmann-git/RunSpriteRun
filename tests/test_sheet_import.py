from pathlib import Path

from PIL import Image

from src.core import blank_sheet, sheet_import
from src.core.systems import get_system
from src.io.save import save_whole

ST = get_system("Atari ST")


def sheet(tmp_path, fill_boxes=(0, 2)):
    im = blank_sheet.build(ST, 8, 8, 3, 2)
    grid = sheet_import.find_grid(im, (0, 255, 0))
    for i in fill_boxes:
        x, y = grid.boxes[i]
        for dx in range(8):
            im.putpixel((x + dx, y + 3), (255, 0, 0))
    p = tmp_path / "mysheet.png"
    im.save(p)
    return p, im


def test_find_grid(tmp_path):
    _, im = sheet(tmp_path)
    g = sheet_import.find_grid(im, (0, 255, 0))
    assert (g.width, g.height, len(g.boxes), g.error) == (8, 8, 6, None)


def test_wrong_box_colour(tmp_path):
    _, im = sheet(tmp_path)
    assert sheet_import.find_grid(im, (1, 2, 3)).error == sheet_import.MSG_NO_BOXES


def test_empty_boxes_left_out(tmp_path):
    _, im = sheet(tmp_path)
    g = sheet_import.find_grid(im, (0, 255, 0))
    res = sheet_import.import_sheet(im, "mysheet", g, (255, 0, 255), ST)
    assert [f.label for f in res.frames] == ["mysheet", "mysheet"]            # named after the sheet; the project numbers them
    assert res.can_create


def test_all_empty(tmp_path):
    _, im = sheet(tmp_path, ())
    g = sheet_import.find_grid(im, (0, 255, 0))
    assert sheet_import.import_sheet(im, "s", g, (255, 0, 255), ST).rejected == sheet_import.MSG_ALL_EMPTY


def test_dialog_and_save_copies_sheet(tmp_path, qtbot=None):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.app.start_project import StartProjectDialog
    p, _ = sheet(tmp_path)
    d = StartProjectDialog(folder=str(tmp_path))
    d.name.setText("Demo")
    d.sheet_radio.setChecked(True)
    d.set_sheet(p)
    assert d.create_btn.isEnabled() and (d.width_box.value(), d.height_box.value()) == (8, 8)
    assert d.file_list.count() == 6
    d._create()
    proj = d.project
    assert len(proj.frames) == 2 and proj.transparent == (255, 0, 255)
    out = tmp_path / "Demo"
    out.mkdir()
    save_whole(proj, out / "Demo.rsr")
    assert (out / "mysheet.png").is_file() and proj.source_sheet is None


def test_too_many_colours_rejects_sheet(tmp_path):
    im = blank_sheet.build(ST, 8, 8, 3, 2)
    g = sheet_import.find_grid(im, (0, 255, 0))
    for i, (x, y) in enumerate(g.boxes):
        for dx in range(8):
            im.putpixel((x + dx, y), (i * 36, 0, 0))
        im.putpixel((x, y + 1), (0, i * 36 + 36, 0))
        im.putpixel((x + 1, y + 1), (0, 0, i * 36 + 36))
    res = sheet_import.import_sheet(im, "s", g, (255, 0, 255), ST)
    assert res.rejected == sheet_import.msg_sheet_colours("Atari ST", 16)


def test_radio_options_exclusive(tmp_path):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.app.start_project import StartProjectDialog
    p, _ = sheet(tmp_path)
    d = StartProjectDialog(folder=str(tmp_path))
    d.show()
    d.files_radio.setChecked(True)
    assert d.files_radio.isChecked() and d.browse.isEnabled() and not d.sheet_browse.isEnabled()
    d.sheet_radio.setChecked(True)
    assert d.sheet_browse.isEnabled() and not d.browse.isEnabled() and not d.width_box.isEnabled()
    d.set_sheet(p)
    assert d.file_list.count() == 6
    d.files_radio.setChecked(True)
    assert d.file_list.count() == 0 and d._sheet_image is None and not d.sheet_browse.isEnabled()
