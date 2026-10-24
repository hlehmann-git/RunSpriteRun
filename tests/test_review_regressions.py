"""Regression checks for defects found in an external review of v2.0.14.

Each test asserts the intended behaviour. Tests still marked xfail(strict=True)
reproduce a defect that has not been fixed yet; remove the mark with the fix.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QComboBox

from src.app import messages
from src.app.control_window import ControlWindow, GroupKeysDialog
from src.app.controller import Controller
from src.app.info_dialogs import HelpDialog
from src.app.main_window import MainWindow
from src.app.start_project import StartProjectDialog
from src.core import blank_sheet, groups
from src.core.project import ControlRule, Frame, Group, Project, Rule
from src.core.runner import Runner
from src.core.systems import get_system
from src.io import rules_export
from src.io.project_file import ProjectFileError, open_project
from src.io.save import save_whole
from src.io.settings import Settings

T = (255, 0, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)


@pytest.fixture(scope="session")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def isolated_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUNSPRITERUN_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("RUNSPRITERUN_SETTINGS", str(tmp_path / "settings.json"))
    (tmp_path / "home").mkdir(exist_ok=True)
    monkeypatch.setattr(messages, "warn", lambda *args, **kwargs: None)
    monkeypatch.setattr(messages, "adjusted", lambda *args, **kwargs: None)
    monkeypatch.setattr(messages, "choose", lambda *args, **kwargs: True)


def project() -> Project:
    return Project(
        "Review", get_system("Atari ST"), 8, 8, transparent=T,
        frames=[Frame(f"Frame_{i + 1:03d}", Image.new("RGB", (8, 8), T)) for i in range(3)],
    )


def test_edit_undo_after_palette_replacement_stays_reopenable(app: QApplication, tmp_path: Path) -> None:
    p = project()
    p.frames[0].image.putpixel((0, 0), RED)
    p.extra_colours = [T, RED, GREEN] + [(r, 36, 0) for r in (0, 36, 73, 109, 146, 182, 219, 255)]
    p.extra_colours += [(r, 73, 0) for r in (0, 36, 73, 109, 146)]
    assert len(p.palette()) == p.system.max_colours == 16
    c = Controller(settings=Settings())
    c.set_project(p)
    e = c.edit
    assert e.begin()
    e.set_active(GREEN)
    assert e.press((1, 1))
    e.release((1, 1))
    assert c.replace_colour(p.palette().index(RED), BLUE)
    assert RED not in p.palette()
    assert e.undo()
    e.finish(True)
    path = tmp_path / "Review.rsr"
    save_whole(p, path)
    q = open_project(path)
    assert RED not in q.palette()


def test_save_refuses_a_palette_over_the_system_limit(tmp_path: Path) -> None:
    p = project()
    p.extra_colours = [T] + [(r, g, 0) for r in (0, 36, 73, 109, 146, 182) for g in (36, 73, 109)]
    assert len(p.palette()) > p.system.max_colours
    with pytest.raises(OSError):
        save_whole(p, tmp_path / "Review.rsr")
    assert not (tmp_path / "Review.rsr").exists()


def test_colour_in_edit_undo_history_cannot_be_deleted(app: QApplication) -> None:
    p = project()
    p.extra_colours = [T, RED, GREEN]
    c = Controller(settings=Settings())
    c.set_project(p)
    e = c.edit
    assert e.begin()
    e.set_active(GREEN)
    assert e.press((1, 1))
    e.release((1, 1))
    e.set_active(RED)
    assert e.press((1, 1))
    e.release((1, 1))
    slot = p.palette().index(GREEN)
    assert not p.colour_is_used(GREEN)
    assert c.delete_colour_blocked(slot) is not None
    e.finish(False)


@pytest.mark.xfail(strict=True, reason="F02: enlarged sheet imports pad with the first sprite pixel")
def test_enlarged_sheet_uses_chosen_transparent_padding(app: QApplication, tmp_path: Path) -> None:
    system = get_system("Atari ST")
    sheet = blank_sheet.build(system, 8, 8, 1, 1, box=GREEN, fill=T)
    sheet.putpixel((1, blank_sheet.BAR_H + 1), RED)
    source = tmp_path / "sheet.png"
    sheet.save(source)
    d = StartProjectDialog()
    try:
        d.name.setText("Padding")
        d.set_sheet(source)
        d.size_radio.setChecked(True)
        d.width_box.setValue(12)
        d.height_box.setValue(12)
        assert d.create_btn.isEnabled()
        d._create()
        assert d.project is not None
        p = d.project
        assert p.frames[0].image.getpixel((0, 0)) == p.transparent
    finally:
        d.deleteLater()


@pytest.mark.xfail(strict=True, reason="F03: Group keys changes bypass the parent window's Cancel")
def test_cancel_control_window_discards_group_key_changes(app: QApplication) -> None:
    p = project()
    p.groups = [Group("Idle", 0, 2, key="A")]
    p.dirty = False
    c = Controller(settings=Settings())
    c.set_project(p)
    window = ControlWindow(None, c)
    window.load()
    keys = GroupKeysDialog(window, c)
    try:
        combo = keys.findChildren(QComboBox)[0]
        combo.setCurrentIndex(combo.findData("D"))
        keys.accept()
        window.reject()
        assert p.groups[0].key == "A"
        assert not p.dirty
    finally:
        keys.deleteLater()
        window.deleteLater()


@pytest.mark.xfail(strict=True, reason="F04: action's 'Stay on last frame' follows the group's default release")
def test_action_default_release_holds_its_last_frame() -> None:
    p = project()
    p.groups = [
        Group("Idle", 0, 0),
        Group("Action", 1, 2, on_release=Rule("frame", "Frame_001")),
    ]
    p.control_rules = [ControlRule(["7"], "Action", once=True)]
    assert groups.rule_problems(p, p.control_rules, []) == {}
    r = Runner(p)
    r.start()
    assert r.press("7")
    r.tick()
    assert r.frame == 2
    r.tick()
    assert r.frame == 2


@pytest.mark.xfail(strict=True, reason="F05: failed rules export is reported as a successful save")
def test_save_reports_required_rules_file_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = project()

    def denied(*args: object, **kwargs: object) -> None:
        raise PermissionError("simulated: rules destination is read-only")

    monkeypatch.setattr(rules_export, "write_rules_files", denied)
    with pytest.raises(OSError):
        save_whole(p, tmp_path / "Review.rsr")


@pytest.mark.xfail(strict=True, reason="F06: Run key routing consumes S before Select tool routing")
def test_s_select_shortcut_through_actual_event_filter(app: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    window = MainWindow(settings=Settings())
    window.set_project(project())
    try:
        assert window.controller.edit.begin()
        monkeypatch.setattr(window, "isActiveWindow", lambda: True)
        monkeypatch.setattr(window, "_text_focus", lambda: False)
        event = QKeyEvent(QEvent.KeyPress, Qt.Key_S, Qt.NoModifier)
        handled = window.eventFilter(window, event)
        assert handled
        assert window.controller.edit.tool == "select"
    finally:
        window.controller.edit.finish(False)
        window.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)


@pytest.mark.xfail(strict=True, reason="F07: F1 shows placeholder text rather than the user guide")
def test_help_contains_real_instructions(app: QApplication) -> None:
    dialog = HelpDialog(None)
    try:
        text = dialog.text.toPlainText()
        assert "Lorem ipsum" not in text
        assert "RunSpriteRun" in text
    finally:
        dialog.deleteLater()


# ---- safe project loading and writing ---------------------------------------------------------------
def _saved_with_group(tmp_path: Path, name: str) -> Path:
    """Save a normal project, then change a group name inside the .rsr the way a hand-edited file would."""
    import json
    import zipfile
    p = project()
    p.groups = [Group("Walk", 0, 2)]
    good = tmp_path / "good" / "Review.rsr"
    good.parent.mkdir()
    save_whole(p, good)
    bad = tmp_path / "Review.rsr"
    with zipfile.ZipFile(good) as zin, zipfile.ZipFile(bad, "w") as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.endswith(".json"):
                meta = json.loads(data)
                if "groups" in meta:
                    meta["groups"][0]["name"] = name
                    data = json.dumps(meta).encode()
            zout.writestr(item, data)
    return bad


@pytest.mark.parametrize("name", ["x\\..\\..\\evil", "../evil", "a:stream", "=HYPERLINK(1)", "", "a b"])
def test_project_with_invalid_group_name_is_refused(tmp_path: Path, name: str) -> None:
    from src.io.project_file import InvalidNameError
    with pytest.raises(InvalidNameError):
        open_project(_saved_with_group(tmp_path, name))


def test_project_with_valid_group_name_still_opens(tmp_path: Path) -> None:
    assert open_project(_saved_with_group(tmp_path, "Walk_Left-2")).groups[0].name == "Walk_Left-2"


@pytest.mark.parametrize("name", ["..\\evil", "../evil", "a:b", "a/b"])
def test_write_refuses_names_that_leave_the_output_folder(tmp_path: Path, name: str) -> None:
    from src.io import export
    p = project()
    p.groups = [Group(name, 0, 2)]
    with pytest.raises(OSError):
        export.write_all(p, tmp_path / "Review", T, with_data=True)
    assert not any(f.name.startswith("evil") for f in tmp_path.rglob("*"))


def test_save_only_deletes_files_it_names_itself(tmp_path: Path) -> None:
    folder = tmp_path / "Review"
    folder.mkdir()
    p = project()
    save_whole(p, folder / "Review.rsr")
    keep = folder / "Sprites" / "Someone_else.png"
    keep.write_bytes(b"not ours")
    stale = folder / "Sprites" / "Review_Old_Frame_009.png"
    stale.write_bytes(b"ours")
    p.written_files = list(p.written_files) + ["Sprites/Someone_else.png", "Sprites/Review_Old_Frame_009.png"]
    save_whole(p, folder / "Review.rsr")
    assert keep.exists()
    assert not stale.exists()


def test_rules_text_cells_are_never_formulas() -> None:
    p = project()
    p.groups = [Group("-Walk", 0, 1), Group("Run", 2, 2, key="D")]
    p.control_rules = [ControlRule(["D"], "-Walk")]
    text = rules_export.rules_text(p)
    for line in text.splitlines():
        for cell in line.split("\t"):
            assert not cell.startswith(("=", "+", "-", "@"))
    assert "'-Walk" in text
