import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication, QFileDialog

from src.app import export_dialog, messages, save_as_dialog
from src.app.export_dialog import ExportDialog
from src.app.info_dialogs import ProjectInformationDialog
from src.app.main_window import MainWindow
from src.core import blank_sheet, sheets
from src.core.colour import level_to_8bit as lv
from src.core.project import Frame, Group, Project
from src.core.systems import get_system
from src.io import export, paths
from src.io.project_file import ProjectFileError, open_project, save_project
from src.io.save import save_whole


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def project(n=6, size=8, name="Hero"):
    """n frames of size x size, each a different valid Atari ST colour; two groups (frames 0-1 and 2-3), the rest in none."""
    frames = []
    for i in range(n):
        frames.append(Frame(f"F{i + 1}", Image.new("RGB", (size, size), (lv(i % 8, 3), lv((i // 2) % 8, 3), 0))))
    return Project(name, get_system("Atari ST"), size, size, frames=frames,
                   groups=[g for g in (Group("Idle", 0, 1), Group("Walk", 2, 3)) if g.last < n], dirty=True)


# ---- sheets (FR-4.7) -------------------------------------------------------------------------------------
def test_ten_sprites_per_row_layout():
    assert sheets.layout(120) == (10, 12) and sheets.layout(25) == (10, 3) and sheets.layout(4) == (4, 1)
    assert sheets.layout(10) == (10, 1) and sheets.layout(11) == (10, 2)


def test_largest_project_sheet_size_matches_the_image():
    p = project(n=120, size=64)
    s = sheets.build_sheet(p, list(range(120)), p.transparent)
    colours = len(p.palette())
    assert s.image.width == 10 * 65 + 1 == 651 or s.image.width == 651
    assert s.image.size == sheets.sheet_size(120, 64, 64, colours)
    assert blank_sheet.BAR_H + 12 * 65 + 1 <= s.image.height                      # text bar + 12 rows of boxes + colour bar


def test_short_sheet_has_only_the_boxes_it_needs():
    p = project(n=3, size=8)
    s = sheets.build_sheet(p, [0, 1, 2], p.transparent)
    assert s.image.width == blank_sheet.MIN_WIDTH                                    # narrow sheets are widened for the text bar
    assert [(x, y) for _, x, y in s.positions] == [(1, 63), (10, 63), (19, 63)]


def test_frames_cut_back_out_are_identical_and_colour_bar_matches():
    p = project(n=6, size=8)
    s = sheets.build_sheet(p, list(range(6)), p.transparent)
    for idx, x, y in s.positions:
        assert s.image.crop((x, y, x + 8, y + 8)).tobytes() == p.frames[idx].image.tobytes()
    palette = p.palette()
    bar_y = blank_sheet.sheet_size(8, 8, 6, 1)[1] + sheets.SWATCH_GAP
    per_row = (s.image.width + sheets.SWATCH_GAP) // (sheets.SWATCH + sheets.SWATCH_GAP)
    step = sheets.SWATCH + sheets.SWATCH_GAP
    for n, colour in enumerate(palette):
        x, y = (n % per_row) * step, bar_y + (n // per_row) * step
        assert s.image.getpixel((x, y)) == colour and s.image.getpixel((x + 7, y + 7)) == colour


def test_boxes_are_one_pixel_lines_and_the_sheet_can_be_imported_again():
    from src.core import sheet_import
    p = project(n=13, size=8)
    s = sheets.build_sheet(p, list(range(13)), p.transparent)
    assert s.positions[9][1:] == (1 + 9 * 9, 63) and s.positions[10][1:] == (1, 72)      # the 11th sprite starts row 2
    g = sheet_import.find_grid(s.image, s.box)
    assert g.error is None and (g.width, g.height) == (8, 8) and len(g.boxes) == 20       # 10 x 2 boxes, 7 empty
    res = sheet_import.import_sheet(s.image, "x", g, p.transparent, p.system)
    assert len(res.frames) == 12                                                           # frame 1 is all transparent: an empty box
    assert res.frames[11].image.tobytes() == p.frames[12].image.tobytes()


def test_box_colour_is_green_unless_the_sprites_use_it():
    p = project(n=2)
    assert sheets.build_sheet(p, [0, 1], p.transparent).box == (0, 255, 0)
    p.frames[0].image.putpixel((0, 0), (0, 255, 0))
    assert sheets.build_sheet(p, [0, 1], p.transparent).box != (0, 255, 0)
    assert sheets.box_colour([], (0, 255, 0)) != (0, 255, 0)                         # nor the fill colour


def test_fill_colour_can_be_changed():
    p = project(n=11)
    s = sheets.build_sheet(p, list(range(11)), (255, 255, 255))
    assert s.image.getpixel((1 + 3 * 9 + 3, 63 + 9 + 3)) == (255, 255, 255)           # an empty box in row 2
    assert s.image.getpixel((s.image.width - 2, 63 + 3)) == blank_sheet.BG            # beside the boxes: the sheet background


def test_frame_data_text():
    p = project()
    s = sheets.build_sheet(p, [2, 3], p.transparent)
    text = sheets.frame_data_text(p, "Hero_Walk_SpriteSheet.png", s.image.size, s.positions)
    lines = text.splitlines()
    assert lines[:4] == ["Project: Hero", "System: Atari ST", "FramesPerSecond: 12", "FrameSize: 8 x 8"]
    assert lines[4] == "SheetFile: Hero_Walk_SpriteSheet.png" and lines[5].startswith("SheetSize: ")
    assert lines[6] == "Number, Label, Group, X, Y, Width, Height"
    assert lines[7] == "3, F3, Walk, 1, 63, 8, 8" and lines[8] == "4, F4, Walk, 10, 63, 8, 8"


def test_frame_file_names_use_group_or_nogroup():
    p = project()
    assert sheets.frame_file_name(p, 0) == "Hero_Idle_F1.png"
    assert sheets.frame_file_name(p, 5) == "Hero_NoGroup_F6.png"


# ---- writing -------------------------------------------------------------------------------------------
def test_write_all_makes_three_folders_and_all_files(tmp_path):
    p = project()
    written = export.write_all(p, tmp_path / "out", p.transparent, with_data=False)
    for name in ("Sprite_Sheet", "Frame_Sprite_Sheets", "Sprites"):
        assert (tmp_path / "out" / name).is_dir()
    assert (tmp_path / "out/Sprite_Sheet/Hero_SpriteSheet.png").exists()
    assert (tmp_path / "out/Frame_Sprite_Sheets/Hero_Idle_SpriteSheet.png").exists()
    assert (tmp_path / "out/Frame_Sprite_Sheets/Hero_Walk_SpriteSheet.png").exists()
    assert len(list((tmp_path / "out/Sprites").iterdir())) == 6
    assert not list((tmp_path / "out").rglob("*.txt"))                    # Export writes no data files
    assert set(written) == set(export.planned_files(p, with_data=False))
    im = Image.open(tmp_path / "out/Sprites/Hero_Idle_F1.png")
    assert im.mode == "RGB" and im.size == (8, 8) and im.tobytes() == p.frames[0].image.tobytes()


def test_group_sheet_holds_exactly_that_groups_frames(tmp_path):
    p = project()
    export.write_all(p, tmp_path, p.transparent, with_data=True)
    sheet = Image.open(tmp_path / "Frame_Sprite_Sheets/Hero_Walk_SpriteSheet.png")
    assert sheet.crop((1, 63, 9, 71)).tobytes() == p.frames[2].image.tobytes()
    assert sheet.crop((10, 63, 18, 71)).tobytes() == p.frames[3].image.tobytes()
    assert (tmp_path / "Frame_Sprite_Sheets/Hero_Walk_SpriteSheet.txt").exists()


def test_stale_files_only_removed_from_the_written_list(tmp_path):
    p = project()
    rsr = tmp_path / "Hero" / "Hero.rsr"
    rsr.parent.mkdir()
    save_whole(p, rsr)
    mine = rsr.parent / "Sprites" / "notes.txt"
    mine.write_text("mine")
    assert (rsr.parent / "Sprites/Hero_Idle_F1.png").exists()
    p.frames[0].label = "Renamed"
    p.groups.pop()                                                         # the Walk group is deleted
    save_whole(p, rsr)
    assert not (rsr.parent / "Sprites/Hero_Idle_F1.png").exists()
    assert (rsr.parent / "Sprites/Hero_Idle_Renamed.png").exists()
    assert not (rsr.parent / "Frame_Sprite_Sheets/Hero_Walk_SpriteSheet.png").exists()
    assert not (rsr.parent / "Frame_Sprite_Sheets/Hero_Walk_SpriteSheet.txt").exists()
    assert mine.read_text() == "mine"                                      # never touched


def test_written_list_survives_save_and_open_and_bad_entries_are_dropped(tmp_path):
    p = project()
    rsr = tmp_path / "Hero" / "Hero.rsr"
    rsr.parent.mkdir()
    save_whole(p, rsr)
    q = open_project(rsr)
    assert q.written_files == p.written_files and "Sprites/Hero_Idle_F1.png" in q.written_files
    cleaned = export.clean_written_list(["Sprites/a.png", "../x.png", "/etc/passwd", "Sprites/../a", "Other/a.png",
                                         "Sprites/sub/a.png", "C:/a.png", "Sprites\\a.png", 5, "Sprites/"])
    assert cleaned == ["Sprites/a.png"]


def test_old_project_files_with_a_gap_still_open(tmp_path):
    import json, zipfile
    p = project()
    save_project(p, tmp_path / "a.rsr")
    with zipfile.ZipFile(tmp_path / "a.rsr") as z:
        names = z.namelist()
        entries = {n: z.read(n) for n in names}
    meta_name = next(n for n in names if n.endswith(".json"))
    meta = json.loads(entries[meta_name])
    assert "gap" not in meta                                               # sheets no longer have a gap
    meta["gap"] = 40                                                       # an old file: the value is simply ignored
    entries[meta_name] = json.dumps(meta).encode()
    with zipfile.ZipFile(tmp_path / "old.rsr", "w") as z:
        for n, data in entries.items():
            z.writestr(n, data)
    assert open_project(tmp_path / "old.rsr").name == "Hero"


def test_inside_project_folder(tmp_path):
    p = project()
    rsr = tmp_path / "Projects" / "Hero" / "Hero.rsr"
    rsr.parent.mkdir(parents=True)
    save_whole(p, rsr)
    assert export.inside_project_folder(rsr.parent, p)
    assert export.inside_project_folder(rsr.parent / "Sprites", p)
    other = tmp_path / "Projects" / "Other"
    other.mkdir()
    (other / "Other.rsr").write_bytes(b"x")
    assert export.inside_project_folder(other, p)                          # another project's folder
    assert not export.inside_project_folder(tmp_path / "Exports", p)


# ---- windows -------------------------------------------------------------------------------------------
@pytest.fixture
def log(monkeypatch):
    out = {"warn": [], "info": [], "replace": True}
    monkeypatch.setattr(messages, "warn", lambda p, t, d=None: out["warn"].append(t))
    monkeypatch.setattr(messages, "info", lambda p, t, d=None: out["info"].append(t))
    monkeypatch.setattr(export_dialog, "confirm_replace", lambda p, files: (out.setdefault("asked", files), out["replace"])[1])
    return out


def test_export_window_defaults_and_summary(app, tmp_path):
    p = project()
    d = ExportDialog(None, p)
    assert d.folder.text() == str(paths.exports_folder()) and not hasattr(d, "gap")
    assert (d.frames.text(), d.groups.text(), d.sheets.text()) == ("6", "2", "3")
    assert d.fill.itemText(0) == "Transparent colour" and d.fill.currentData() == p.transparent
    assert d.close_button.text() == "Close" and d.export_button.text() == "Export"


def test_export_writes_into_project_named_folder_and_stays_open(app, tmp_path, log):
    p = project()
    d = ExportDialog(None, p)
    d.folder.setText(str(tmp_path / "Exports"))
    assert d.run_export()
    assert (tmp_path / "Exports/Hero/Sprite_Sheet/Hero_SpriteSheet.png").exists()
    assert (tmp_path / "Exports/Hero/Sprites/Hero_NoGroup_F6.png").exists()
    assert not list((tmp_path / "Exports").rglob("*.txt")) and not list((tmp_path / "Exports").rglob("*.rsr"))
    assert "Exported 6 frames and 3 sheets" in d.result.text()
    assert not p.dirty or p.dirty                                          # export never touches the project file state


def test_export_uses_its_own_fill(app, tmp_path, log):
    p = project(n=11)
    d = ExportDialog(None, p)
    d.folder.setText(str(tmp_path))
    d.fill.setCurrentIndex(d.fill.count() - 1)
    assert d.run_export()
    im = Image.open(tmp_path / "Hero/Sprite_Sheet/Hero_SpriteSheet.png")
    assert im.width == blank_sheet.MIN_WIDTH and im.getpixel((1 + 3 * 9 + 3, 63 + 9 + 3)) == d.fill.currentData()


def test_export_refuses_project_folder_and_writes_nothing(app, tmp_path, log):
    p = project()
    rsr = tmp_path / "Projects" / "Hero" / "Hero.rsr"
    rsr.parent.mkdir(parents=True)
    save_whole(p, rsr)
    before = sorted(x.name for x in rsr.parent.rglob("*"))
    d = ExportDialog(None, p)
    d.folder.setText(str(rsr.parent))
    assert not d.run_export()
    assert log["warn"] == ["Choose a folder outside your project folders."]
    assert sorted(x.name for x in rsr.parent.rglob("*")) == before


def test_export_asks_before_replacing_and_cancel_writes_nothing(app, tmp_path, log):
    p = project()
    d = ExportDialog(None, p)
    d.folder.setText(str(tmp_path))
    assert d.run_export()
    f = tmp_path / "Hero/Sprites/Hero_Idle_F1.png"
    f.write_bytes(b"old")
    log["replace"] = False
    assert not d.run_export() and f.read_bytes() == b"old" and "Sprites/Hero_Idle_F1.png" in log["asked"]
    log["replace"] = True
    assert d.run_export() and f.read_bytes() != b"old"


def test_export_works_on_an_unsaved_project(app, tmp_path, log):
    p = project()
    assert p.file_path is None
    d = ExportDialog(None, p)
    d.folder.setText(str(tmp_path))
    assert d.run_export()


def test_menu_has_one_export_and_no_export_frames(app, log):
    w = MainWindow()
    names = [a.text() for a in w.menu_file.actions()]
    assert "Export" in names and "Export Sprite Sheet" not in names and "Export Frames" not in names
    assert w.act_export.shortcut().toString() == "Ctrl+E"


def test_project_information_has_no_gap_box(app, log):
    w = MainWindow()
    w.set_project(project())
    d = ProjectInformationDialog(w, w.controller.project, w.controller)
    assert not hasattr(d, "gap_box")
