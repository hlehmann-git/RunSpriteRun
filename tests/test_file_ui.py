import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
import zipfile

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication, QFileDialog, QPushButton

from src.app import messages, save_as_dialog
from src.app.info_dialogs import AboutDialog, HelpDialog, ProjectInformationDialog, information_rows
from src.app.main_window import MainWindow
from src.app.settings_dialog import SettingsDialog
from src.core.colour import level_to_8bit as lv
from src.core.project import Frame, Group, Project
from src.core.systems import get_system
from src.io import settings as settings_io
from src.io.project_file import open_project, save_project


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def log(monkeypatch):
    out = {"warn": [], "choose": [], "answer": True, "save_changes": "discard"}
    monkeypatch.setattr(messages, "warn", lambda p, t, d=None: out["warn"].append(t))
    monkeypatch.setattr(messages, "info", lambda p, t, d=None: None)
    monkeypatch.setattr(messages, "choose", lambda p, t, d, y, n: (out["choose"].append(t), out["answer"])[1])
    monkeypatch.setattr(messages, "save_changes", lambda p, name: out["save_changes"])
    return out


def make(name="P", dirty=False):
    f1 = Image.new("RGB", (8, 8), (0, 0, 0))
    f2 = Image.new("RGB", (8, 8), (lv(7, 3), 0, 0))
    return Project(name, get_system("Atari ST"), 8, 8, frames=[Frame("f1", f1), Frame("f2", f2)],
                   groups=[Group("G", 0, 1)], dirty=dirty)


@pytest.fixture
def win(app, log):
    w = MainWindow()
    w.show()
    w.set_project(make(dirty=True))                               # a new project counts as unsaved
    return w


def dialogs(monkeypatch, open_path=None, save_as=None):
    """save_as: None = cancel, or (name, parent folder), or a list of those (the box opens again after a message)."""
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (open_path or "", "")))
    answers = save_as if isinstance(save_as, list) else [save_as]
    seen = []
    monkeypatch.setattr(save_as_dialog, "ask", lambda parent, name, folder: (seen.append((name, folder)),
                                                                          answers.pop(0) if answers else None)[1])
    return seen


def test_save_as_makes_project_folder_then_save_state(win, tmp_path, monkeypatch):
    p = win.controller.project
    assert win.act_save.isEnabled()                              # never saved: always available
    dialogs(monkeypatch, save_as=("Hero", str(tmp_path)))
    win.act_save_as.trigger()
    target = tmp_path / "Hero" / "Hero.rsr"                      # the project folder holds the .rsr
    assert target.exists() and p.file_path == str(target) and not p.dirty
    assert p.name == "Hero"                                      # Save As makes a new project: renamed
    assert open_project(target).name == "Hero"
    assert not win.act_save.isEnabled()                          # nothing new to save
    win.controller.rename(0, "walk")                              # frame 1 is in the only group: both rename
    assert win.act_save.isEnabled() and p.dirty
    win.act_save.trigger()
    assert open_project(target).frames[0].label == "walk_001" and not win.act_save.isEnabled()


def test_save_on_never_saved_project_uses_save_as(win, tmp_path, monkeypatch):
    seen = dialogs(monkeypatch, save_as=("A", str(tmp_path)))
    win.act_save.trigger()
    assert (tmp_path / "A" / "A.rsr").exists()
    assert seen == [("P", str(tmp_path / "home" / "Projects"))]    # starts with the project name and Projects


def test_save_clears_undo_history(win, tmp_path, monkeypatch):
    c = win.controller
    c.rename(0, "walk")
    assert c.can_undo
    dialogs(monkeypatch, save_as=("A", str(tmp_path)))
    win.act_save.trigger()
    assert not c.can_undo and not win.act_undo.isEnabled()


def test_save_as_name_rule_reopens_box(win, tmp_path, log, monkeypatch):
    seen = dialogs(monkeypatch, save_as=[("my file", str(tmp_path)), ("my_file", str(tmp_path))])
    assert win.save_as()
    assert log["warn"] == ["Project names can only use letters, numbers, - and _ (no spaces)."]
    assert (tmp_path / "my_file" / "my_file.rsr").exists() and not (tmp_path / "my file").exists()
    assert seen[1] == ("my file", str(tmp_path))                 # the box opens again with what was typed


def test_save_as_existing_folder_is_refused(win, tmp_path, log, monkeypatch):
    (tmp_path / "Taken").mkdir()
    dialogs(monkeypatch, save_as=[("Taken", str(tmp_path)), ("Free", str(tmp_path))])
    assert win.save_as()
    assert log["warn"] == [f"A project called Taken already exists in {tmp_path}. Choose another name."]
    assert (tmp_path / "Free" / "Free.rsr").exists() and not list((tmp_path / "Taken").iterdir())


def test_save_as_second_time_leaves_the_first_project(win, tmp_path, monkeypatch):
    dialogs(monkeypatch, save_as=[("One", str(tmp_path)), ("Two", str(tmp_path))])
    assert win.save_as() and win.save_as()
    assert open_project(tmp_path / "One" / "One.rsr").name == "One"
    assert open_project(tmp_path / "Two" / "Two.rsr").name == "Two"
    assert win.controller.project.file_path == str(tmp_path / "Two" / "Two.rsr")


def test_save_as_cancel(win, monkeypatch):
    dialogs(monkeypatch, save_as=None)
    assert not win.save_as() and win.controller.project.file_path is None


def test_save_failure_keeps_project_unsaved(win, tmp_path, log, monkeypatch):
    blocker = tmp_path / "file.txt"
    blocker.write_text("x")                                      # a file where the parent folder should be
    dialogs(monkeypatch, save_as=("X", str(blocker / "sub")))
    assert not win.save_as()
    assert log["warn"] and "could not be saved" in log["warn"][0]
    p = win.controller.project
    assert p.dirty and p.file_path is None and p.name == "P"


def test_info_bar_follows_project(win, tmp_path, monkeypatch):
    bar = win.info_bar
    assert bar.label.text() == "Project: P   |   System: Atari ST   |   Frames: 2   |   Frame Groups: 1"
    dialogs(monkeypatch, save_as=("Renamed", str(tmp_path)))
    win.save_as()
    assert bar.label.text().startswith("Project: Renamed   |")
    win.controller.project.groups.clear()
    win.controller.frames_changed.emit()
    assert bar.label.text().endswith("Frame Groups: 0")


def test_save_no_longer_reminds_about_labels(win, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(messages, "info", lambda p, t, d=None: shown.append(t))
    dialogs(monkeypatch, save_as=("R", str(tmp_path)))
    assert win.save_as() and shown == []                                               # the red-label reminder is gone
    assert not any(f.copied for f in open_project(tmp_path / "R" / "R.rsr").frames)


def test_open_replaces_project_and_clears_history(win, tmp_path, monkeypatch):
    other = make("Other")
    path = tmp_path / "Other.rsr"
    save_project(other, path)
    win.controller.rename(0, "x")
    dialogs(monkeypatch, open_path=str(path))
    win.act_open.trigger()                                       # unsaved change, prompt answers Don't Save
    assert win.controller.project.name == "Other" and not win.controller.can_undo
    assert not win.act_save.isEnabled()


def test_open_damaged_file_stays(win, tmp_path, log, monkeypatch):
    bad = tmp_path / "bad.rsr"
    bad.write_bytes(b"not a zip")
    before = win.controller.project
    dialogs(monkeypatch, open_path=str(bad))
    win.act_open.trigger()
    assert win.controller.project is before
    assert log["warn"] == ["bad.rsr could not be opened. It may be damaged or saved by a different version of RunSpriteRun."]


def test_unsaved_prompt_cancel_and_save(win, tmp_path, log, monkeypatch):
    p = win.controller.project
    log["save_changes"] = "cancel"
    assert not win.confirm_close()
    other = tmp_path / "O.rsr"
    save_project(make("O"), other)
    dialogs(monkeypatch, open_path=str(other))
    win.act_open.trigger()                                       # Cancel: stays in the project
    assert win.controller.project is p
    log["save_changes"] = "save"
    dialogs(monkeypatch, save_as=("S", str(tmp_path)))
    assert win.confirm_close() and (tmp_path / "S" / "S.rsr").exists()
    assert win.confirm_close()                                   # saved now: no prompt needed


def test_close_event_prompts(win, log):
    log["save_changes"] = "cancel"
    assert not win.close()
    log["save_changes"] = "discard"
    assert win.close()


def test_new_project_prompts_first(win, log, monkeypatch):
    shown = []
    monkeypatch.setattr(win, "show_start_project", lambda: shown.append(1))
    log["save_changes"] = "cancel"
    win.act_new.trigger()
    assert shown == []
    log["save_changes"] = "discard"
    win.act_new.trigger()
    assert shown == [1]


def test_information_rows_follow_prd(win):
    p = win.controller.project
    rows = dict(information_rows(p))
    assert list(rows) == ["Project name", "File location", "Target system", "Max sprite colours", "Bits per channel",
                          "Colour depth", "Total palette colours", "Frame size", "Frames", "Frame Groups",
                          "Frames per second", "Colours in use"]
    assert rows["File location"] == "Not saved yet" and rows["Colours in use"] == "2 / 16"
    assert rows["Bits per channel"] == "3 bits, RGB 3:3:3" and rows["Colour depth"] == "9-bit"
    assert rows["Total palette colours"] == "512" and rows["Frame size"] == "8 x 8"
    ProjectInformationDialog(win, p)


def test_help_and_about_text(win):
    assert len(HelpDialog(win).text.toPlainText().splitlines()) == 10
    a = AboutDialog(win)
    assert a.author.text() == "by Harley Lehmann" and a.version.text() == "Version 2.0.4"
    assert "5649" in a.comments.text() and not a.picture.pixmap().isNull()
    assert a.picture.pixmap().width() == 480
    assert "Deluxe Paint" in a.description.text() and "Buddy Claude" in a.small_print.text()
    assert "PySide6" in a.small_print.text()


def test_settings_window_shows_project_fps(win):
    d = SettingsDialog(win)
    assert [b.text() for b in d.findChildren(QPushButton)] == ["OK", "Cancel"]
    assert [d.fps.itemText(i) for i in range(d.fps.count())] == ["3", "6", "12", "24"]
    assert d.fps.currentText() == str(win.controller.project.fps)
    d.show()
    d.findChildren(QPushButton)[1].click()
    assert not d.isVisible()


def test_settings_ok_changes_project_fps_and_undo(win):
    c = win.controller
    assert c.project.fps == 12
    d = SettingsDialog(win)
    d.fps.setCurrentText("24")
    d.show()
    d.findChildren(QPushButton)[0].click()
    assert c.project.fps == 24 and c.can_undo
    d2 = SettingsDialog(win)
    assert d2.fps.currentText() == "24"
    d2.fps.setCurrentText("6")
    d2.show()
    d2.findChildren(QPushButton)[1].click()          # Cancel changes nothing
    assert c.project.fps == 24
    c.undo()
    assert c.project.fps == 12


def test_settings_menu_needs_a_project(app):
    from src.app.main_window import MainWindow
    w = MainWindow()
    assert not w.act_settings.isEnabled()


def test_settings_ok_saves_and_applies(win, tmp_path, monkeypatch):
    c = win.controller
    view = win.panels["Frame view"].view
    assert view.grid is True
    c.apply_settings(settings_io.Settings(False, "groups"))
    assert view.grid is False
    assert settings_io.load().export_mode == "groups"
    c.set_fps(24)
    assert c.project.fps == 24 and c.can_undo
    c.undo()
    assert c.project.fps == 12


def test_settings_file_missing_or_damaged(tmp_path):
    assert settings_io.load(tmp_path / "none.json") == settings_io.Settings()
    bad = tmp_path / "bad.json"
    bad.write_text("{oops")
    assert settings_io.load(bad) == settings_io.Settings()
    part = tmp_path / "part.json"
    part.write_text(json.dumps({"gap": 99, "grid": False, "export_mode": "x"}))
    s = settings_io.load(part)
    assert s.grid is False and s.export_mode == "sheet"


def test_help_about_menu_actions_need_project(app):
    w = MainWindow()
    assert not w.act_help.isEnabled() and not w.act_about.isEnabled()


def test_projects_folder_and_dialog_start_folders(win, tmp_path, monkeypatch):
    from src.io import paths
    home = tmp_path / "home"
    assert paths.home_folder() == home
    assert paths.projects_folder() == home / "Projects" and (home / "Projects").is_dir()
    seen = {}
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda parent, title, folder, *a: (seen.setdefault("open", folder), "")[1:] + ("",)))
    win.act_open.trigger()
    assert seen["open"] == str(home / "Projects")              # .rsr files live in Projects by default
    asked = dialogs(monkeypatch, save_as=None)
    win.save_as()
    assert asked == [("P", str(home / "Projects"))]            # Save As starts in Projects


def test_image_browse_starts_in_home(app, tmp_path):
    from src.app.start_project import StartProjectDialog
    assert StartProjectDialog()._folder == str(tmp_path / "home")
