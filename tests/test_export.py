import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication, QFileDialog

from src.app import export_dialog, messages, save_as_dialog
from src.app.export_dialog import ExportDialog
from src.app.info_dialogs import ProjectInformationDialog
from src.app.main_window import MainWindow
from src.core import sheets
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
def test_frames_per_row_rule():
    assert sheets.frames_per_row(64, 4) == 30
    assert sheets.frames_per_row(4, 4) == 256
    assert sheets.frames_per_row(64, 0) == 32


def test_largest_project_sheet_is_2036_wide_4_rows():
    p = project(n=120, size=64)
    s = sheets.build_sheet(p, list(range(120)), 4, p.transparent)
    colours = len(p.palette())
    assert s.image.width == 2036
    assert s.image.height == 4 * 64 + 3 * 4 + 4 + (-(-colours // ((2036 + 4) // 12)) * 8 + (-(-colours // ((2036 + 4) // 12)) - 1) * 4)
    assert sheets.sheet_size(120, 64, 64, 4, colours) == s.image.size


def test_short_sheet_is_only_as_wide_as_its_frames():
    p = project(n=3, size=8)
    s = sheets.build_sheet(p, [0, 1, 2], 4, p.transparent)
    assert s.image.width == 3 * 8 + 2 * 4


def test_frames_cut_back_out_are_identical_and_colour_bar_matches():
    p = project(n=6, size=8)
    s = sheets.build_sheet(p, list(range(6)), 4, p.transparent)
    for idx, x, y in s.positions:
        assert s.image.crop((x, y, x + 8, y + 8)).tobytes() == p.frames[idx].image.tobytes()
    palette = p.palette()
    bar_y = 8 + 4
    per_row = (s.image.width + 4) // 12
    for n, colour in enumerate(palette):
        x, y = (n % per_row) * 12, bar_y + (n // per_row) * 12
        assert s.image.getpixel((x, y)) == colour and s.image.getpixel((x + 7, y + 7)) == colour
    assert s.image.getpixel((8, 0)) == p.transparent                     # the gap is the fill colour


def test_fill_colour_can_be_changed():
    p = project(n=2)
    s = sheets.build_sheet(p, [0, 1], 4, (255, 255, 255))
    assert s.image.getpixel((8, 0)) == (255, 255, 255)


def test_frame_data_text():
    p = project()
    s = sheets.build_sheet(p, [2, 3], 4, p.transparent)
    text = sheets.frame_data_text(p, "Hero_Walk_SpriteSheet.png", s.image.size, s.positions)
    lines = text.splitlines()
    assert lines[:4] == ["Project: Hero", "System: Atari ST", "FramesPerSecond: 12", "FrameSize: 8 x 8"]
    assert lines[4] == "SheetFile: Hero_Walk_SpriteSheet.png" and lines[5].startswith("SheetSize: ")
    assert lines[6] == "Number, Label, Group, X, Y, Width, Height"
    assert lines[7] == "3, F3, Walk, 0, 0, 8, 8" and lines[8] == "4, F4, Walk, 12, 0, 8, 8"


def test_frame_file_names_use_group_or_nogroup():
    p = project()
    assert sheets.frame_file_name(p, 0) == "Hero_Idle_F1.png"
    assert sheets.frame_file_name(p, 5) == "Hero_NoGroup_F6.png"


# ---- writing -------------------------------------------------------------------------------------------
def test_write_all_makes_three_folders_and_all_files(tmp_path):
    p = project()
    written = export.write_all(p, tmp_path / "out", 4, p.transparent, with_data=False)
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
    export.write_all(p, tmp_path, 4, p.transparent, with_data=True)
    sheet = Image.open(tmp_path / "Frame_Sprite_Sheets/Hero_Walk_SpriteSheet.png")
    assert sheet.crop((0, 0, 8, 8)).tobytes() == p.frames[2].image.tobytes()
    assert sheet.crop((12, 0, 20, 8)).tobytes() == p.frames[3].image.tobytes()
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
    assert q.written_files == p.written_files and "Sprites/Hero_Idle_F1.png" in q.written_files and q.gap == 4
    cleaned = export.clean_written_list(["Sprites/a.png", "../x.png", "/etc/passwd", "Sprites/../a", "Other/a.png",
                                         "Sprites/sub/a.png", "C:/a.png", "Sprites\\a.png", 5, "Sprites/"])
    assert cleaned == ["Sprites/a.png"]


def test_gap_is_saved_and_checked(tmp_path):
    p = project()
    p.gap = 9
    save_project(p, tmp_path / "a.rsr")
    assert open_project(tmp_path / "a.rsr").gap == 9
    p.gap = 40
    save_project(p, tmp_path / "b.rsr")
    with pytest.raises(ProjectFileError):
        open_project(tmp_path / "b.rsr")


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
    p.gap = 6
    d = ExportDialog(None, p)
    assert d.folder.text() == str(paths.exports_folder()) and d.gap.value() == 6
    assert (d.frames.text(), d.groups.text(), d.sheets.text()) == ("6", "2", "3")
    assert d.fill.itemText(0) == "Transparent colour" and d.fill.currentData() == p.transparent
    assert d.close_button.text() == "Close" and d.export_button.text() == "Export"
    d.gap.setValue(2)
    assert p.gap == 6                                                      # changing the gap here is for this export only


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


def test_export_uses_its_own_gap_and_fill(app, tmp_path, log):
    p = project(n=2)
    d = ExportDialog(None, p)
    d.folder.setText(str(tmp_path))
    d.gap.setValue(2)
    d.fill.setCurrentIndex(d.fill.count() - 1)
    assert d.run_export()
    im = Image.open(tmp_path / "Hero/Sprite_Sheet/Hero_SpriteSheet.png")
    assert im.width == 2 * 8 + 2 and im.getpixel((9, 0)) == d.fill.currentData()


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


def test_project_information_gap_box_is_undoable(app, log):
    w = MainWindow()
    w.set_project(project())
    d = ProjectInformationDialog(w, w.controller.project, w.controller)
    assert d.gap_box.value() == 4
    d.gap_box.setValue(8)
    d.accept()
    assert w.controller.project.gap == 8 and w.controller.project.dirty
    assert w.controller.undo() and w.controller.project.gap == 4


def test_save_as_writes_everything_and_save_cleans_up(app, tmp_path, log, monkeypatch):
    w = MainWindow()
    w.set_project(project())
    monkeypatch.setattr(save_as_dialog, "ask", lambda parent, name, folder: ("Hero2", str(tmp_path)))
    assert w.save_as()
    folder = tmp_path / "Hero2"
    assert (folder / "Hero2.rsr").exists()
    assert (folder / "Sprite_Sheet/Hero2_SpriteSheet.png").exists() and (folder / "Sprite_Sheet/Hero2_SpriteSheet.txt").exists()
    assert (folder / "Frame_Sprite_Sheets/Hero2_Idle_SpriteSheet.png").exists()
    assert (folder / "Sprites/Hero2_NoGroup_F6.png").exists()
    p = w.controller.project
    w.controller.rename(0, "Renamed")
    assert w.save()
    assert not (folder / "Sprites/Hero2_Idle_F1.png").exists() and (folder / "Sprites/Hero2_Idle_Renamed.png").exists()


def test_save_as_into_a_new_folder_starts_empty(app, tmp_path, log, monkeypatch):
    w = MainWindow()
    w.set_project(project())
    answers = [("A", str(tmp_path)), ("B", str(tmp_path))]
    monkeypatch.setattr(save_as_dialog, "ask", lambda parent, name, folder: answers.pop(0))
    assert w.save_as()
    w.controller.rename(0, "Other")
    assert w.save_as()
    assert (tmp_path / "A/Sprites/A_Idle_F1.png").exists()                 # the first project's files are left as they were
    assert (tmp_path / "B/Sprites/B_Idle_Other.png").exists() and not (tmp_path / "B/Sprites/B_Idle_F1.png").exists()


def test_save_of_a_file_outside_its_own_folder_becomes_save_as(app, tmp_path, log, monkeypatch):
    p = project()
    save_project(p, tmp_path / "loose.rsr")                                # the old layout: a loose .rsr
    w = MainWindow()
    w.set_project(open_project(tmp_path / "loose.rsr"))
    w.controller.project.dirty = True
    asked = []
    monkeypatch.setattr(save_as_dialog, "ask", lambda parent, name, folder: (asked.append(1), None)[1])
    assert not w.save() and asked == [1]
    assert not (tmp_path / "Sprites").exists()                             # nothing was dumped next to the loose file
