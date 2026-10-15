import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from src.app import messages
from src.app.group_preview import caption_text
from src.app.main_window import MainWindow
from src.app.start_state_dialog import StartStateDialog
from src.core.project import Frame, Group, Project, Rule
from src.core.systems import get_system


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def log(monkeypatch):
    out = {"warn": [], "info": [], "choose": [], "answer": True}
    monkeypatch.setattr(messages, "warn", lambda p, t, d=None: out["warn"].append(t))
    monkeypatch.setattr(messages, "info", lambda p, t, d=None: out["info"].append(t))
    monkeypatch.setattr(messages, "choose", lambda p, t, d, y, n: (out["choose"].append(t), out["answer"])[1])
    out["copy"] = False                                       # the answer to the overlap message: copy or OK
    monkeypatch.setattr(messages, "overlap", lambda p, t: (out["warn"].append(t), out["copy"])[1])
    return out


def make_project(groups=()):
    frames = [Frame(f"f{i + 1}", Image.new("RGB", (8, 8), (73 * (i % 3), 0, 0))) for i in range(12)]
    return Project("P", get_system("Amiga"), 8, 8, fps=24, frames=frames, groups=list(groups), dirty=False)


@pytest.fixture
def win(app, log):
    w = MainWindow()
    w.show()
    w.set_project(make_project([Group("Idle", 0, 3, key="S", on_release=Rule("group", "Idle", True)),
                                Group("Right", 4, 7, key="D")]))
    return w


def panel(w):
    return w.panels["Set Frame Group"]


def fill(p, name, first, last, key="None"):
    p.name.setText(name)
    p.from_box.setValue(first)
    p.to_box.setValue(last)
    p.key.setCurrentText(key)


def test_menu_states(win):
    assert win.act_new_group.isEnabled() and win.act_start_state.isEnabled()
    assert win.act_delete_group.isEnabled()                   # frame 1 is in group Idle
    win.controller.select(9)                                  # a frame in no group: empty panel
    assert not win.act_delete_group.isEnabled()
    panel(win)._chosen(1)
    assert win.act_delete_group.isEnabled()
    panel(win).new_group()
    assert not win.act_delete_group.isEnabled()


def test_new_group_applies_and_shows_in_timeline_and_preview(win, log):
    p = panel(win)
    p.new_group()
    assert p.name.text() == "" and p.key.currentText() == "None" and p.release.rule().kind == "frame"
    fill(p, "Jump", 9, 11, "W")
    assert p.apply() is True
    g = [g for g in win.controller.project.groups if g.name == "Jump"][0]
    assert (g.first, g.last, g.key) == (8, 10, "W") and p.current == "Jump" and win.controller.project.dirty
    tl = win.panels["Timeline and frames"]
    tl.scroll_by(3)
    assert tl.slots[5].group.text() == "Jump"
    prev = win.panels["Frame Group Preview"]
    assert [prev.chooser.itemText(i) for i in range(prev.chooser.count())] == ["Idle", "Right", "Jump"]


def test_overlap_and_name_errors_keep_everything(win, log):
    p = panel(win)
    p.new_group()
    fill(p, "Bad", 3, 6)
    assert p.apply() is False
    assert log["warn"][-1] == "Frames 4 to 4 already belong to group Idle. Groups cannot overlap." or "already belong" in log["warn"][-1]
    fill(p, "bad name", 9, 10)
    assert p.apply() is False and "no spaces" in log["warn"][-1]
    fill(p, "idle", 9, 10)
    assert p.apply() is False and "already exists" in log["warn"][-1]
    assert len(win.controller.project.groups) == 2


def test_key_move_asks_and_cancel_changes_nothing(win, log):
    p = panel(win)
    p.new_group()
    fill(p, "Jump", 9, 10, "S")
    log["answer"] = False
    assert p.apply() is False and log["choose"][-1] == "Move key S from Idle to Jump?"
    assert win.controller.project.groups[0].key == "S" and len(win.controller.project.groups) == 2
    log["answer"] = True
    assert p.apply() is True
    keys = {g.name: g.key for g in win.controller.project.groups}
    assert keys == {"Idle": None, "Right": "D", "Jump": "S"}


def test_edit_and_rename_updates_rules(win):
    p = panel(win)
    p._chosen(1)                                              # Idle
    assert p.name.text() == "Idle" and p.from_box.value() == 1 and p.to_box.value() == 4 and p.key.currentText() == "S"
    assert p.release.rule() == Rule("group", "Idle", True)
    p.name.setText("Rest")
    assert p.apply()
    g = win.controller.project.groups[0]
    assert g.name == "Rest" and g.on_release.target == "Rest"


def test_delete_group_confirm_and_rules_reset_message(win, log):
    win.controller.project.groups[1].on_release = Rule("group", "Idle")
    win.controller.set_start_state(Rule("group", "Idle"))
    panel(win)._chosen(1)
    log["answer"] = False
    win.delete_group()
    assert len(win.controller.project.groups) == 2 and log["choose"][-1] == "Delete group Idle? Its frames stay in the timeline."
    log["answer"] = True
    win.delete_group()
    p = win.controller.project
    assert [g.name for g in p.groups] == ["Right"] and p.start_state is None and p.groups[0].on_release is None
    assert log["info"][-1] == ("These rules pointed to Idle and have been reset: "
                               "group Right (On Release), Start state.")
    assert panel(win).current is None


def test_start_state_dialog(win, app):
    d = StartStateDialog(win, win.controller.project)
    assert d.rule() == Rule("frame", "f1")                    # never set: Go To Frame 1
    d.editor.radio_group.setChecked(True)
    d.editor.group_combo.setCurrentIndex(1)
    d.editor.loop.setChecked(True)
    win.controller.set_start_state(d.rule())
    assert win.controller.project.start_state == Rule("group", "Right", True)
    d2 = StartStateDialog(win, win.controller.project)
    assert d2.editor.radio_group.isChecked() and d2.editor.loop.isChecked() and d2.editor.group_combo.currentText() == "Right"


def test_preview_plays_group_loop_only_when_play_is_clicked(win):
    prev = win.panels["Frame Group Preview"]
    prev.chooser.setCurrentText("Right")
    prev.chooser.activated.emit(prev.chooser.currentIndex())
    assert not prev.timer.isActive()                           # choosing a group never starts it
    assert prev.caption.text() == "Right · F05–F08" == caption_text("Right", 4, 7)
    prev.play_btn.click()
    assert prev.timer.isActive() and prev.timer.interval() == round(1000 / 24)
    seen = [win.panels["Timeline and frames"].playing]
    for _ in range(5):
        prev._tick()
        seen.append(win.panels["Timeline and frames"].playing)
    assert seen == [4, 5, 6, 7, 4, 5]                          # first frame to last, then repeats
    prev.play_btn.click()                                      # the same button switches it off
    assert not prev.timer.isActive() and win.panels["Timeline and frames"].playing == -1
    prev.play_btn.click()
    assert prev.timer.isActive() and win.panels["Timeline and frames"].playing == 4


def test_selecting_a_frame_shows_its_group_or_an_empty_panel(win):
    p = panel(win)
    assert p.current == "Idle" and p.name.text() == "Idle" and p.key.currentText() == "S"
    assert (p.from_box.value(), p.to_box.value()) == (1, 4) and p.apply_btn.isEnabled()
    win.controller.select(5)
    assert p.current == "Right" and p.name.text() == "Right" and p.key.currentText() == "D"
    assert (p.from_box.value(), p.to_box.value()) == (5, 8)
    win.controller.select(10)                                 # in no group: nothing shown
    assert p.current is None and p.blank and p.name.text() == "" and p.chooser.currentIndex() == -1
    assert not p.name.isEnabled() and not p.apply_btn.isEnabled() and p.from_box.text().strip() == ""
    win.controller.select(2)
    assert p.current == "Idle" and not p.blank and p.name.isEnabled()


def test_new_group_from_an_empty_panel_starts_at_the_selected_frame(win):
    p = panel(win)
    win.controller.select(10)
    p.new_group()
    assert not p.blank and p.name.isEnabled() and (p.from_box.value(), p.to_box.value()) == (11, 11)
    win.controller.select(11)                                 # still a new group; From/To follow the frame
    assert not p.blank and p.current is None and (p.from_box.value(), p.to_box.value()) == (12, 12)


def test_selecting_a_frame_shows_it_in_the_preview_without_playing(win):
    pv = win.panels["Frame Group Preview"]
    win.controller.select(5)
    assert pv.chooser.currentText() == "Right" and not pv.timer.isActive()
    assert pv.view._image is win.controller.project.frames[5].image
    win.controller.select(10)                                 # in no group: blank drop-down, frame still shown
    assert pv.chooser.currentIndex() == -1 and not pv.play_btn.isEnabled() and pv.caption.text() == ""
    assert pv.view._image is win.controller.project.frames[10].image
    win.controller.select(1)
    assert pv.chooser.currentText() == "Idle" and not pv.timer.isActive()


def test_selecting_a_frame_stops_a_playing_preview(win):
    pv = win.panels["Frame Group Preview"]
    win.controller.select(5)
    pv.play_btn.click()
    assert pv.timer.isActive()
    win.controller.select(6)
    assert not pv.timer.isActive() and win.panels["Timeline and frames"].playing == -1


def test_clicking_a_timeline_frame_updates_every_view(win):
    tl = win.panels["Timeline and frames"]
    tl.slots[5].thumb.pressed.emit(5)
    p = win.controller.project
    assert win.controller.selected == 5
    assert panel(win).current == "Right"                       # Set Frame Group shows the frame's group
    assert win.panels["Frame view"].view._image is p.frames[5].image
    assert win.panels["Frame Group Preview"].view._image is p.frames[5].image
    assert win.panels["RunSpriteRun window"].view._image is p.frames[5].image
    tl.bar.setValue(1)
    tl.slots[7].thumb.pressed.emit(7)                          # frame 9 (the timeline shows 8 frames at a time)
    assert panel(win).blank
    assert win.panels["RunSpriteRun window"].view._image is p.frames[8].image


def test_frame_view_arrows_step_through_all_frames(win):
    fv = win.panels["Frame view"]
    c = win.controller
    c.select(0)
    assert not fv.prev_btn.isEnabled() and fv.next_btn.isEnabled()
    fv.next_btn.click()
    assert c.selected == 1 and fv.prev_btn.isEnabled()
    c.select(len(c.project.frames) - 1)
    assert not fv.next_btn.isEnabled() and fv.prev_btn.isEnabled()
    fv.prev_btn.click()
    assert c.selected == len(c.project.frames) - 2          # not limited to a group


def test_preview_arrows_step_within_the_group_and_wrap(win):
    prev = win.panels["Frame Group Preview"]
    c = win.controller
    prev.chooser.setCurrentText("Right")
    prev.chooser.activated.emit(prev.chooser.currentIndex())
    g = prev._group()
    selected = c.selected
    prev.fwd_btn.click()
    assert prev._shown == g.first + 1 and c.selected == selected     # only the preview changes
    for _ in range(g.last - g.first):
        prev.fwd_btn.click()
    assert prev._shown == g.first                                    # went forward past the last frame: wrapped round
    prev.back_btn.click()
    assert prev._shown == g.last                                     # back from the first frame: wrapped round
    prev.play_btn.click()
    assert prev.timer.isActive() and prev.play_btn.isChecked()
    prev.fwd_btn.click()
    assert not prev.timer.isActive() and not prev.play_btn.isChecked()   # an arrow pauses playback


def test_key_list_has_the_four_diagonals_with_clear_names(win):
    p = panel(win)
    names = [p.key.itemText(i) for i in range(p.key.count())]
    assert "W+A (up-left)" in names and "W+D (up-right)" in names and "S+D (down-right)" in names and "S+A (down-left)" in names
    p.key.setCurrentIndex(p.key.findData("W+D"))
    assert p.key.currentData() == "W+D" and p.key.currentText() == "W+D (up-right)"
