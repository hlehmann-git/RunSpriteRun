import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from src.app.main_window import MainWindow
from src.core import layers as L
from src.core.project import Frame, Project
from src.core.systems import get_system
from src.io.project_file import open_project, save_project

T = (0, 0, 0)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def make_project(n=2, size=8):
    sysm = get_system("Sega Genesis / Mega Drive")
    img = Image.new("RGB", (size, size), T)
    img.putpixel((1, 1), (255, 0, 0))
    frames = [Frame(f"F{i + 1}", img.copy()) for i in range(n)]
    return Project(name="Edit", system=sysm, width=size, height=size, transparent=T, frames=frames)


@pytest.fixture
def win(app):
    w = MainWindow()
    w.set_project(make_project())
    assert w.controller.edit.begin()
    return w


def stroke(e, tool, a, b, shift=False):
    e.set_tool(tool)
    assert e.press(a, shift)
    e.move(b, shift)
    e.release(b, shift)


def test_never_edited_frame_lands_on_core(win):
    p = win.controller.project
    layers = L.layers_of(p.frames[0], p.transparent)
    assert layers[L.CORE] is p.frames[0].image and layers[L.FG].getpixel((0, 0)) == T


def test_pencil_paints_the_active_colour_on_core_only_and_is_one_undo_step(win):
    c, e = win.controller, win.controller.edit
    e.set_active((255, 0, 0))
    e.set_option("pencil", "pixel_perfect", False)
    stroke(e, "pencil", (2, 2), (6, 2))
    f = c.project.frames[0]
    assert [f.image.getpixel((x, 2)) for x in range(2, 7)] == [(255, 0, 0)] * 5
    assert f.layers[L.FG].getpixel((3, 2)) == T and f.layers[L.CORE].getpixel((3, 2)) == (255, 0, 0)
    assert e.undo() and c.project.frames[0].layers is None and c.project.frames[0].image.getpixel((3, 2)) == T
    assert not e.can_undo and not c.can_undo


def test_eraser_paints_the_transparent_colour(win):
    e = win.controller.edit
    stroke(e, "eraser", (1, 1), (1, 1))
    assert win.controller.project.frames[0].image.getpixel((1, 1)) == T


def test_a_stroke_that_changes_nothing_is_not_an_undo_step(win):
    e = win.controller.edit
    stroke(e, "eraser", (5, 5), (6, 6))
    assert not e.can_undo


def test_hidden_or_unticked_layers_cannot_be_drawn_on(win):
    e = win.controller.edit
    e.set_visible(L.CORE, False)
    assert not e.press((1, 1))
    e.set_visible(L.CORE, True)
    e.set_target(L.CORE, False)
    assert not e.press((1, 1))


def test_layers_flatten_foreground_over_core_over_background(win):
    c, e = win.controller, win.controller.edit
    e.set_active((255, 0, 0))
    e.set_target(L.CORE, False)
    e.set_target(L.BG, True)
    stroke(e, "pencil", (4, 4), (4, 4))            # red on BackGround
    p = c.project
    assert p.frames[0].image.getpixel((4, 4)) == (255, 0, 0)
    e.set_target(L.BG, False)
    e.set_target(L.FG, True)
    e.set_active(p.palette()[0])
    stroke(e, "pencil", (4, 4), (4, 4))
    assert p.frames[0].layers[L.BG].getpixel((4, 4)) == (255, 0, 0)
    e.set_visible(L.FG, False)
    assert e.display_image(0).getpixel((4, 4)) == (255, 0, 0)


def test_move_clips_at_the_frame_edge_without_wrapping(win):
    c, e = win.controller, win.controller.edit
    stroke(e, "move", (3, 3), (10, 3))           # 7 pixels right: the pixel at x=1 leaves the frame
    f = c.project.frames[0]
    assert all(f.image.getpixel((x, y)) == T for x in range(8) for y in range(8))


def test_move_moves_the_whole_layer_and_leaves_transparent_behind(win):
    c, e = win.controller, win.controller.edit
    stroke(e, "move", (3, 3), (5, 4))
    f = c.project.frames[0]
    assert f.image.getpixel((3, 2)) == (255, 0, 0) and f.image.getpixel((1, 1)) == T


def test_move_is_not_applied_until_released_so_dragging_back_restores(win):
    c, e = win.controller, win.controller.edit
    e.set_tool("move")
    e.press((3, 3))
    e.move((20, 3))
    assert c.project.frames[0].image.getpixel((1, 1)) == T
    e.move((3, 3))
    e.release((3, 3))
    assert c.project.frames[0].image.getpixel((1, 1)) == (255, 0, 0) and not e.can_undo


def test_shapes_and_shift(win):
    c, e = win.controller, win.controller.edit
    e.set_active((255, 0, 0))
    e.set_option("square", "filled", True)
    stroke(e, "square", (2, 2), (5, 3), shift=True)
    img = c.project.frames[0].image
    assert img.getpixel((5, 5)) == (255, 0, 0) and img.getpixel((6, 6)) == T


def test_bucket_fills_the_top_ticked_layer(win):
    c, e = win.controller, win.controller.edit
    e.set_active((255, 0, 0))
    e.set_target(L.FG, True)
    stroke(e, "bucket", (5, 5), (5, 5))
    f = c.project.frames[0]
    assert f.layers[L.FG].getpixel((7, 7)) == (255, 0, 0) and f.layers[L.CORE].getpixel((7, 7)) == T


def test_plus_colour_adds_to_the_palette_and_is_limited(win):
    c, e = win.controller, win.controller.edit
    p = c.project
    e.editor_colour = (0, 0, 255)
    assert e.can_add_colour() and e.add_colour()
    assert (0, 0, 255) in p.palette()
    e.finish(False)
    assert (0, 0, 255) not in p.palette()
    e.begin()
    for i in range(1, 20):
        e.editor_colour = (36 * (i % 8), 36 * (i // 8), 36)
        e.add_colour()
    assert len(p.palette()) <= p.system.max_colours


def test_actions_flip_mirror_rotate(win):
    c, e = win.controller, win.controller.edit
    assert e.action("mirror")
    assert c.project.frames[0].image.getpixel((6, 1)) == (255, 0, 0)
    assert e.action("flip")
    assert c.project.frames[0].image.getpixel((6, 6)) == (255, 0, 0)
    assert e.action("rotate_left") and e.undo()


def test_layers_survive_save_and_open(win, tmp_path):
    c, e = win.controller, win.controller.edit
    e.set_target(L.FG, True)
    e.set_active((255, 0, 0))
    stroke(e, "pencil", (4, 4), (4, 4))
    path = tmp_path / "x.rsr"
    save_project(c.project, path)
    back = open_project(path)
    assert back.frames[0].layers is not None and back.frames[1].layers is None
    assert back.frames[0].layers[L.FG].getpixel((4, 4)) == (255, 0, 0)
    assert back.frames[0].image.tobytes() == c.project.frames[0].image.tobytes()


def test_extra_colours_survive_save_and_open(win, tmp_path):
    c, e = win.controller, win.controller.edit
    e.editor_colour = (0, 0, 255)
    e.add_colour()
    save_project(c.project, tmp_path / "y.rsr")
    assert (0, 0, 255) in open_project(tmp_path / "y.rsr").palette()


def test_replacing_a_palette_colour_recolours_the_layers(win):
    c, e = win.controller, win.controller.edit
    e.set_target(L.FG, True)
    e.set_active((255, 0, 0))
    stroke(e, "pencil", (4, 4), (4, 4))
    assert c.replace_colour(c.project.palette().index((255, 0, 0)), (0, 0, 255))
    f = c.project.frames[0]
    assert f.layers[L.FG].getpixel((4, 4)) == (0, 0, 255) and f.image.getpixel((4, 4)) == (0, 0, 255)


def test_edit_panel_toggle_and_options(win, monkeypatch):
    from src.app import messages
    monkeypatch.setattr(messages, "apply_edit", lambda parent: "discard")
    panel = win.panels["Keys"]
    e = win.controller.edit
    assert panel.work.isEnabled() and panel.edit_btn.isChecked()
    panel.v1_btn.click()
    assert not e.mode and not panel.work.isEnabled()
    e.begin()
    panel.tool_buttons["square"].click()
    assert e.tool == "square" and panel.options_title.text() == "OPTIONS · Square"
    assert panel.tool_buttons["select"].isEnabled()
    panel.targets[0].click()
    assert e.target[0] is True


def test_frame_view_draws_with_the_mouse(win):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    fv = win.panels["Frame view"]
    v = fv.view
    e = win.controller.edit
    e.set_tool("pencil")
    e.set_active((255, 0, 0))
    # sprite is 8 px in a 512 px view, scale 64: pixel (5, 5) is around (5*64+32, 5*64+32)
    QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier, QPoint(5 * 64 + 32, 5 * 64 + 32))
    assert win.controller.project.frames[0].image.getpixel((5, 5)) == (255, 0, 0)


# ---- starting and leaving Edit mode -------------------------------------------------------------------
@pytest.fixture
def fresh(app):
    w = MainWindow()
    w.set_project(make_project(n=4))
    return w


def test_new_frame_is_blank_gets_a_label_and_is_inserted_where_asked(fresh):
    c, e = fresh.controller, fresh.controller.edit
    c.select(1)
    assert e.begin(new=True, where="after")
    p = c.project
    assert [f.label for f in p.frames][2] == "Frame_5" and c.selected == 2 and len(p.frames) == 5
    assert p.frames[2].image.getcolors() == [(64, T)]
    e.finish(False)
    assert len(p.frames) == 4 and c.selected == 1                      # discarding leaves no trace
    assert e.begin(new=True, where="first") and c.project.frames[0].label == "Frame_5" and c.selected == 0
    e.finish(True)
    assert len(c.project.frames) == 5 and c.can_undo and c.undo() and len(c.project.frames) == 4


def test_new_frame_can_start_as_a_copy(fresh):
    c, e = fresh.controller, fresh.controller.edit
    assert e.begin(new=True, where="before", copy=True)
    assert c.project.frames[0].image.getpixel((1, 1)) == (255, 0, 0)
    e.finish(False)


def named_project(labels):
    from src.core.project import Group
    p = make_project(n=len(labels))
    for f, lab in zip(p.frames, labels):
        f.label = lab
    return p


@pytest.fixture
def grouped(app):
    from src.core.project import Group, Rule
    w = MainWindow()
    p = named_project(["Idle_1", "Idle_2", "Idle_3", "Idle_4", "Jump_1", "Jump_2"])
    p.groups = [Group("Idle", 0, 3, on_release=Rule("frame", "Idle_4")), Group("Jump", 4, 5)]
    p.start_state = Rule("frame", "Idle_3")
    w.set_project(p)
    return w


def labels(w):
    return [f.label for f in w.controller.project.frames]


def test_new_frame_in_a_group_takes_its_label_and_renumbers_the_rest(grouped):
    c, e = grouped.controller, grouped.controller.edit
    p = c.project
    c.select(2)
    assert e.begin(new=True, where="after")
    assert labels(grouped) == ["Idle_1", "Idle_2", "Idle_3", "Idle_4", "Idle_5", "Jump_1", "Jump_2"]
    assert [(g.first, g.last) for g in p.groups] == [(0, 4), (5, 6)]
    assert p.groups[0].on_release.target == "Idle_5" and p.start_state.target == "Idle_3"     # rules follow the renamed frames
    e.finish(False)                                                       # discarding puts every label back
    assert labels(grouped)[:5] == ["Idle_1", "Idle_2", "Idle_3", "Idle_4", "Jump_1"] and p.groups[0].on_release.target == "Idle_4"
    c.select(2)
    e.begin(new=True, where="after")
    e.finish(True)
    assert c.undo() and labels(grouped)[3] == "Idle_4" and len(p.frames) == 6    # one Undo step brings everything back


def test_inserting_at_either_end_of_a_group_extends_it(grouped):
    c, e = grouped.controller, grouped.controller.edit
    p = c.project
    c.select(3)
    e.begin(new=True, where="after")                                      # after the last Idle frame
    assert labels(grouped)[3:6] == ["Idle_4", "Idle_5", "Jump_1"] and (p.groups[0].first, p.groups[0].last) == (0, 4)
    e.finish(False)
    c.select(4)
    e.begin(new=True, where="before")                                     # before the first Jump frame
    assert labels(grouped)[4:7] == ["Jump_1", "Jump_2", "Jump_3"] and (p.groups[1].first, p.groups[1].last) == (4, 6)
    e.finish(False)
    c.select(4)
    e.begin(new=True, where="first")                                      # Frame 1 stays outside unless Frame 1 is selected
    assert p.frames[0].label == "Frame_7" and (p.groups[0].first, p.groups[0].last) == (1, 4)
    e.finish(False)
    c.select(0)
    e.begin(new=True, where="first")
    assert p.frames[0].label == "Idle_1" and (p.groups[0].first, p.groups[0].last) == (0, 4)
    e.finish(False)


def test_renumbering_only_goes_as_far_as_needed_and_keeps_zero_padding(app):
    from src.core.project import Group
    w = MainWindow()
    p = named_project(["Run_1", "Run_2", "Run_4", "Other"])
    p.groups = [Group("Run", 0, 2)]
    w.set_project(p)
    w.controller.select(1)
    w.controller.edit.begin(new=True, where="after")
    assert labels(w) == ["Run_1", "Run_2", "Run_3", "Run_4", "Other"]      # Run_4 had room: nothing renamed
    w.controller.edit.finish(False)
    p2 = named_project(["Hit_01", "Hit_02", "Hit_03"])
    p2.groups = [Group("Hit", 0, 2)]
    w.set_project(p2)
    w.controller.select(0)
    w.controller.edit.begin(new=True, where="after")
    assert labels(w) == ["Hit_01", "Hit_02", "Hit_03", "Hit_04"]


def test_mixed_labels_or_clashes_fall_back_to_a_frame_label(app):
    from src.core.project import Group
    w = MainWindow()
    p = named_project(["Idle_1", "Wobble", "Idle_2", "Jump_1"])
    p.groups = [Group("Idle", 0, 2)]
    w.set_project(p)
    w.controller.select(0)
    w.controller.edit.begin(new=True, where="after")
    assert labels(w)[1] == "Frame_5" and p.groups[0].last == 3
    w.controller.edit.finish(False)
    p2 = named_project(["Idle_1", "Idle_2", "Idle_3"])
    p2.groups = [Group("Idle", 0, 1)]
    w.set_project(p2)
    w.controller.select(0)
    w.controller.edit.begin(new=True, where="after")
    assert labels(w)[1] == "Frame_4"                                       # Idle_3 is taken by a frame outside the group


def test_frame_limit_stops_a_new_frame(fresh):
    from src.core.edit import EditError
    from src.core.rules import MAX_FRAMES
    c, e = fresh.controller, fresh.controller.edit
    c.project.frames.extend(Frame(f"X{i}", c.project.frames[0].image) for i in range(MAX_FRAMES - 4))
    with pytest.raises(EditError):
        e.begin(new=True)
    assert not e.mode


def test_apply_is_one_undo_step_and_discard_restores_everything(fresh):
    c, e = fresh.controller, fresh.controller.edit
    e.begin()
    e.set_active((255, 0, 0))
    stroke(e, "pencil", (4, 4), (6, 4))
    stroke(e, "pencil", (4, 6), (6, 6))
    assert not c.can_undo                                              # nothing is final yet
    e.finish(True)
    assert c.project.frames[0].image.getpixel((5, 4)) == (255, 0, 0) and c.can_undo
    assert c.undo() and c.project.frames[0].image.getpixel((5, 4)) == T and not c.can_undo
    e.begin()
    e.set_active((255, 0, 0))
    stroke(e, "pencil", (4, 4), (6, 4))
    e.finish(False)
    assert c.project.frames[0].image.getpixel((5, 4)) == T and not c.can_undo


def test_leaving_without_changes_needs_no_question(fresh, monkeypatch):
    from src.app import edit_flow, messages
    monkeypatch.setattr(messages, "apply_edit", lambda parent: pytest.fail("should not ask"))
    assert fresh.controller.edit.begin() and edit_flow.leave(fresh, fresh.controller.edit)
    e = fresh.controller.edit
    e.begin()
    e.set_active((255, 0, 0))
    stroke(e, "pencil", (4, 4), (4, 4))
    monkeypatch.setattr(messages, "apply_edit", lambda parent: "keep")
    assert not edit_flow.leave(fresh, e) and e.mode
    monkeypatch.setattr(messages, "apply_edit", lambda parent: "apply")
    assert edit_flow.leave(fresh, e) and not e.mode


def test_edit_mode_greys_out_panels_and_menus(fresh, monkeypatch):
    from src.app import messages
    shown = []
    monkeypatch.setattr(messages, "info", lambda p, t, d=None: shown.append(t))
    e = fresh.controller.edit
    assert fresh.panels["Set Frame Group"].isEnabled() and fresh.panels["RunSpriteRun window"].isEnabled()
    e.begin()
    assert not fresh.panels["Set Frame Group"].isEnabled() and not fresh.panels["RunSpriteRun window"].isEnabled()
    assert not fresh.act_new_group.isEnabled() and fresh.panels["Frame Group Preview"].isEnabled()
    fresh.save()
    fresh.new_project()
    fresh.show_export()
    assert len(shown) == 3 and fresh.controller.running is False
    fresh.controller.toggle_run()
    assert not fresh.controller.running
    assert not fresh.controller.rename(0, "Other") and not fresh.controller.move_frame(0, 1)
    e.finish(False)
    assert fresh.panels["Set Frame Group"].isEnabled()


def test_other_frames_are_view_only(fresh):
    c, e = fresh.controller, fresh.controller.edit
    e.begin()
    c.select(1)
    fv = fresh.panels["Frame view"]
    assert fv.edit_note.text() == "VIEW ONLY" and not fv.view.draggable
    e.set_tool("pencil")
    assert not e.press((2, 2))
    c.select(0)
    assert fv.edit_note.text() == "EDITING" and fv.view.draggable
    e.finish(False)


def test_edit_undo_redo_follow_the_menu(fresh):
    c, e = fresh.controller, fresh.controller.edit
    e.begin()
    e.set_active((255, 0, 0))
    stroke(e, "pencil", (4, 4), (4, 4))
    assert fresh.act_undo.isEnabled() and not fresh.act_redo.isEnabled()
    fresh.act_undo.trigger()
    assert c.project.frames[0].image.getpixel((4, 4)) == T and fresh.act_redo.isEnabled()
    fresh.act_redo.trigger()
    assert c.project.frames[0].image.getpixel((4, 4)) == (255, 0, 0)
    e.finish(False)


# ---- primary and secondary colour, shapes ---------------------------------------------------------------
def test_outline_and_fill_uses_both_colours(win):
    c, e = win.controller, win.controller.edit
    p = c.project
    e.editor_colour = (0, 0, 255)
    e.add_colour()
    e.set_colours((255, 0, 0), (0, 0, 255))
    e.set_option("square", "style", "Outline + Fill")
    stroke(e, "square", (1, 3), (6, 7))
    img = c.project.frames[0].image
    assert img.getpixel((1, 3)) == (255, 0, 0) and img.getpixel((3, 5)) == (0, 0, 255)
    e.set_option("square", "style", "Filled")
    stroke(e, "square", (1, 3), (6, 7))
    assert c.project.frames[0].image.getpixel((3, 5)) == (255, 0, 0)


def test_other_tools_ignore_the_secondary_colour(win):
    c, e = win.controller, win.controller.edit
    e.editor_colour = (0, 0, 255)
    e.add_colour()
    e.set_colours((255, 0, 0), (0, 0, 255))
    e.set_option("pencil", "pixel_perfect", False)
    stroke(e, "pencil", (4, 4), (5, 4))
    assert {c.project.frames[0].image.getpixel(p) for p in ((4, 4), (5, 4))} == {(255, 0, 0)}


def test_circle_outline_at_thickness_one_has_no_doubled_corners():
    from src.core.tools import circle_parts
    outline, whole = circle_parts((0, 0), (8, 8), 1, False, False)
    assert len(outline) == 20 and outline <= whole
    assert not any({(x + 1, y), (x, y + 1), (x + 1, y + 1)} <= outline for x, y in outline)      # no 2 x 2 blocks


def test_eraser_has_no_pixel_perfect_option_and_thickness_starts_at_one(win):
    from src.app.edit_session import DEFAULT_OPTIONS
    assert DEFAULT_OPTIONS["eraser"]["pixel_perfect"] is False
    assert all(DEFAULT_OPTIONS[t]["thickness"] == 1 for t in ("pencil", "eraser", "line", "square", "circle"))
    panel = win.panels["Keys"]
    panel.tool_buttons["eraser"].click()
    assert "Pixel Perfect" not in [b.text() for b in panel.scroll.widget().findChildren(type(panel.edit_btn))] and not [
        w for w in panel.scroll.widget().children() if getattr(w, "text", lambda: "")() == "Pixel Perfect"]


def test_colour_editor_primary_secondary(win):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    c, e = win.controller, win.controller.edit
    ed = win.panels["Colour editor"]
    e.editor_colour = (0, 0, 255)
    e.add_colour()
    pal = c.project.palette()
    assert ed.cols["primary"] == e.active and ed.preview.size().width() == 36
    c.palette_clicked.emit(1)
    assert e.active == pal[1]
    c.palette_right_clicked.emit(2)
    assert e.secondary == pal[2] and ed.current == "secondary"
    ed._square_picked(10, 10, "primary")
    assert ed.current == "primary" and e.active == ed.colour
    ed._pair_clicked("secondary")
    assert ed.current == "secondary" and ed.colour == e.secondary
    ed.eyedropper.click()
    c.frame_pixel_right_clicked.emit((255, 0, 0))
    assert e.secondary == (255, 0, 0)


def test_mirror_vertical_line_mirrors_left_to_right(win):
    c, e = win.controller, win.controller.edit
    e.set_active((255, 0, 0))
    e.toggle_mirror("v")
    assert e.mirror_armed == "v" and not e.press((2, 2))          # armed: a click places the line, it does not draw
    assert e.place_mirror(4.2, 3.0) and e.mirror["v"] == 8 and e.mirror_armed is None   # nearest edge: between pixels 3 and 4
    stroke(e, "pencil", (1, 5), (1, 5))
    f = c.project.frames[0]
    assert f.image.getpixel((1, 5)) == (255, 0, 0) and f.image.getpixel((6, 5)) == (255, 0, 0)
    assert e.undo()
    assert c.project.frames[0].image.getpixel((6, 5)) == T and c.project.frames[0].image.getpixel((1, 5)) == T


def test_mirror_both_lines_and_centre_line_and_off_frame(win):
    c, e = win.controller, win.controller.edit
    e.set_active((255, 0, 0))
    e.toggle_mirror("v")
    e.place_mirror(2.6, 0)                                        # nearest edge: after pixel 2 (half pixels: 6)
    e.toggle_mirror("h")
    e.place_mirror(0, 3.9)                                        # edge below pixel 3 (half pixels: 8)
    stroke(e, "pencil", (1, 1), (1, 1))
    im = c.project.frames[0].image
    assert [im.getpixel(p) for p in ((1, 1), (4, 1), (1, 6), (4, 6))] == [(255, 0, 0)] * 4
    assert e.mirror == {"v": 6, "h": 8}
    stroke(e, "pencil", (0, 0), (0, 0))                           # its mirror x = 5 is inside; y mirror 7 inside
    stroke(e, "pencil", (7, 0), (7, 0))                           # mirror x = -2 is outside the frame and left out
    assert c.project.frames[0].image.getpixel((7, 0)) == (255, 0, 0)


def test_mirror_icon_toggles_off_and_clears_on_leaving(win):
    e = win.controller.edit
    e.toggle_mirror("h")
    e.toggle_mirror("h")
    assert e.mirror_armed is None and e.mirror["h"] is None
    e.toggle_mirror("h")
    e.place_mirror(0, 2)
    e.toggle_mirror("h")
    assert e.mirror["h"] is None
    e.toggle_mirror("v")
    e.place_mirror(3, 0)
    e.finish(False)
    assert e.mirror == {"v": None, "h": None}


def test_undo_redo_buttons(win):
    c, e = win.controller, win.controller.edit
    from src.app.edit_panel import EditPanel
    panel = win.findChild(EditPanel)
    assert not panel.actions["undo"].isEnabled() and not panel.actions["redo"].isEnabled()
    e.set_active((255, 0, 0))
    stroke(e, "pencil", (4, 4), (4, 4))
    assert panel.actions["undo"].isEnabled() and not panel.actions["redo"].isEnabled()
    panel.actions["undo"].click()
    assert c.project.frames[0].image.getpixel((4, 4)) == T and panel.actions["redo"].isEnabled()
    panel.actions["redo"].click()
    assert c.project.frames[0].image.getpixel((4, 4)) == (255, 0, 0)


def test_edit_mode_uses_the_larger_frame_view_layout_and_leaving_restores_it(win):
    w, e = win, win.controller.edit
    fv, tl = w.panels["Frame view"], w.panels["Timeline and frames"]
    assert fv.view.width() == 512 and fv.width() == 544
    assert w.panels["Set Frame Group"].isHidden() and w.panels["RunSpriteRun window"].isHidden()
    assert w.panels["Frame Group Preview"].x() == 576 and tl.y() >= fv.y() + fv.height()
    e.finish(False)
    assert fv.view.width() == 256 and fv.width() == 288
    assert not w.panels["Set Frame Group"].isHidden() and w.panels["Palette panel"].x() == 928


def test_zoom_and_pan_in_the_frame_view(win):
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtTest import QTest
    c, e = win.controller, win.controller.edit
    fv = win.panels["Frame view"]
    v = fv.view
    assert v.navigable and v.current_scale() == v.fit() == 64        # an 8 px sprite fills the 512 px view
    p = c.project
    big = Image.new("RGB", (64, 64), T)
    big.putpixel((10, 10), (255, 0, 0))
    p.frames[0].image = big                                         # a 64 px sprite: fit is 8x
    fv._show(0)
    assert v.fit() == 8 and not fv.zoom_out.isEnabled()
    fv.zoom_in.click()
    assert v.current_scale() == 9 and fv.zoom_out.isEnabled() and "9x" in fv.zoom_label.text()
    v.set_scale(16)
    left_before = v._geometry()[2]
    v._start_pan(QPointF(200, 200))
    v._pan_to(QPointF(150, 200))                                    # dragging left moves the picture left
    v._panning = None
    assert v._geometry()[2] < left_before
    # drawing still hits the pixel under the mouse after zoom and pan
    e.set_active((255, 0, 0))
    e.set_option("pencil", "pixel_perfect", False)
    _d, s, ox, oy, _w, _h = v._geometry()
    pt = QPoint(ox + 20 * s + s // 2, oy + 20 * s + s // 2)
    QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier, pt)
    assert p.frames[0].image.getpixel((20, 20)) == (255, 0, 0)
    # the zoom stays while stepping between frames and goes back to fit when Edit mode ends
    c.select(1)
    assert v.current_scale() == 16 or v.scale == 16
    e.finish(False)
    assert v.scale is None and not fv.zoom_in.isVisible()


def test_zoom_keeps_the_point_under_the_pointer_and_grid_lines_stay_one_pixel(win):
    from PySide6.QtCore import QPointF
    from src.app.render import render_window
    fv = win.panels["Frame view"]
    v = fv.view
    win.controller.project.frames[0].image = Image.new("RGB", (64, 64), (255, 255, 255))
    fv._show(0)
    v.set_scale(12, QPointF(100, 100))
    px = v.pixel_at(QPointF(100, 100))
    v.set_scale(20, QPointF(100, 100))
    assert v.pixel_at(QPointF(100, 100)) == px
    im = render_window(Image.new("RGB", (4, 4), (255, 255, 255)), T, 64, 64, 16, 0, 0, True)
    assert [im.getpixel((x, 5)) for x in (14, 15, 16)] == [(255, 255, 255), (0, 0, 0), (255, 255, 255)]


def test_tools_have_their_own_pointer_in_the_frame_view(win):
    from PySide6.QtCore import Qt
    e, v = win.controller.edit, win.panels["Frame view"].view
    e.set_tool("pencil")
    assert v.cursor().pixmap().width() > 0 and v.cursor().hotSpot().y() > 16     # the pencil's tip
    e.set_tool("move")
    assert v.cursor().shape() == Qt.SizeAllCursor
    e.set_tool("pencil")
    e.toggle_mirror("v")
    assert v.cursor().shape() == Qt.CrossCursor                                # placing a guide line
    e.finish(False)
    assert v.cursor().shape() == Qt.ArrowCursor


def test_rotate_and_flip_buttons_act_on_the_ticked_layers(win):
    from src.app.edit_panel import EditPanel
    c, e = win.controller, win.controller.edit
    panel = win.findChild(EditPanel)
    assert list(panel.actions) == ["mirror_v", "mirror_h", "rotate_right", "rotate_left", "rotate_180", "flip_h", "flip_v", "undo", "redo"]
    red = (255, 0, 0)
    f = lambda: c.project.frames[0].image
    assert f().getpixel((1, 1)) == red
    panel.actions["flip_h"].click()
    assert f().getpixel((6, 1)) == red
    panel.actions["flip_v"].click()
    assert f().getpixel((6, 6)) == red
    panel.actions["rotate_180"].click()
    assert f().getpixel((1, 1)) == red
    panel.actions["rotate_right"].click()                       # (x, y) -> (7 - y, x)
    assert f().getpixel((6, 1)) == red
    panel.actions["rotate_left"].click()
    assert f().getpixel((1, 1)) == red
    for _ in range(5):
        panel.actions["undo"].click()
    assert f().getpixel((1, 1)) == red and not panel.actions["undo"].isEnabled()


# ---- Select, Cut, Copy, Paste, Delete -----------------------------------------------------------------------
RED = (255, 0, 0)


def select(e, a, b):
    e.set_tool("select")
    assert e.press(a)
    e.move(b)
    e.release(b)


def test_select_drags_a_rectangle_click_deselects_and_inside_drag_moves_the_outline(win):
    e = win.controller.edit
    select(e, (1, 1), (3, 2))
    assert e.selection == (1, 1, 4, 3) and e.sel_idx == 0
    select(e, (2, 2), (4, 3))                                  # inside: moves the outline, not the pixels
    assert e.selection == (3, 2, 6, 4)
    assert win.controller.project.frames[0].image.getpixel((1, 1)) == RED
    select(e, (7, 7), (7, 7))                                  # a click outside without dragging deselects
    assert e.selection is None
    select(e, (5, 5), (12, 12))                                # cut to the frame
    assert e.selection == (5, 5, 8, 8)
    assert e.select_all() and e.selection == (0, 0, 8, 8)


def test_copy_paste_floats_then_enter_fixes_in_one_undo_step(win):
    c, e = win.controller, win.controller.edit
    f = lambda: c.project.frames[0].image
    select(e, (1, 1), (2, 2))
    assert e.copy() and e.clipboard["w"] == 2
    assert e.paste() and e.floating is not None and f().getpixel((0, 0)) == RED and f().getpixel((1, 1)) == RED   # top left
    e.set_tool("move")
    assert e.press((0, 0))
    e.move((3, 3))
    e.release((3, 3))
    assert f().getpixel((3, 3)) == RED and f().getpixel((0, 0)) == T and e.floating["x"] == 3   # dragged by (3, 3)
    assert e.fix() and e.floating is None and e.selection is None
    assert f().getpixel((3, 3)) == RED and f().getpixel((1, 1)) == RED
    assert e.undo() and f().getpixel((3, 3)) == T and f().getpixel((1, 1)) == RED     # one Undo step


def test_escape_discards_a_floating_paste_and_undo_does_the_same(win):
    c, e = win.controller, win.controller.edit
    f = lambda: c.project.frames[0].image
    select(e, (1, 1), (2, 2))
    e.copy()
    e.paste()
    e.nudge(2, 2)
    assert f().getpixel((2, 2)) == RED
    assert e.escape() and e.floating is None and f().getpixel((2, 2)) == T and not e._undo
    e.paste()
    assert e.undo() and e.floating is None and f().getpixel((0, 0)) == T


def test_paste_is_see_through_and_floating_blocks_other_frames_and_drawing(win):
    c, e = win.controller, win.controller.edit
    c.project.frames[0].image.putpixel((1, 0), (0, 0, 255))                    # something under a transparent pixel of the paste
    select(e, (1, 1), (2, 2))                                                  # holds one red pixel and 3 transparent
    e.copy()
    e.paste()
    assert c.project.frames[0].image.getpixel((1, 0)) == (0, 0, 255)           # the transparent pixel did not overwrite it
    c.select(1)
    assert c.selected == 0                                                     # blocked while floating
    e.set_tool("pencil")
    assert not e.press((5, 5))
    e.fix()
    c.select(1)
    assert c.selected == 1


def test_cut_and_delete_clear_the_selection_on_ticked_layers_only(win):
    c, e = win.controller, win.controller.edit
    f = lambda: c.project.frames[0].image
    select(e, (1, 1), (1, 1))
    select(e, (0, 0), (2, 2))
    assert e.cut() and f().getpixel((1, 1)) == T and e.clipboard is not None
    assert e.undo() and f().getpixel((1, 1)) == RED
    assert e.delete() and f().getpixel((1, 1)) == T
    assert e.paste() and e.fix() and f().getpixel((1, 1)) == RED


def test_move_tool_moves_only_the_selected_pixels_and_arrow_keys_nudge(win):
    c, e = win.controller, win.controller.edit
    f = lambda: c.project.frames[0].image
    f().putpixel((6, 6), (0, 0, 255))
    select(e, (0, 0), (2, 2))
    e.set_tool("move")
    assert e.press((1, 1))
    e.move((3, 2))
    e.release((3, 2))
    assert f().getpixel((3, 2)) == RED and f().getpixel((1, 1)) == T and f().getpixel((6, 6)) == (0, 0, 255)
    assert e.selection == (2, 1, 5, 4)
    assert e.nudge(1, 0) and f().getpixel((4, 2)) == RED and e.selection == (3, 1, 6, 4)


def test_flip_and_rotate_buttons_turn_only_the_selection(win):
    c, e = win.controller, win.controller.edit
    f = lambda: c.project.frames[0].image
    select(e, (0, 0), (2, 2))                                                  # 3 x 3 square holding red at (1, 1)
    f().putpixel((0, 0), (0, 0, 255))
    c.project.frames[0].image = f()
    assert e.can_rotate()
    e.action("flip_h")
    assert f().getpixel((2, 0)) == (0, 0, 255) and f().getpixel((1, 1)) == RED
    select(e, (4, 4), (7, 5))                                                  # 4 x 2: not square
    assert not e.can_rotate()


def test_copied_pixels_follow_a_replaced_palette_colour(win):
    c, e = win.controller, win.controller.edit
    select(e, (1, 1), (1, 1))
    select(e, (0, 0), (2, 2))
    e.copy()
    e.finish(False)
    e.begin()                                                                  # the clipboard survives a new Edit session
    p = c.project
    slot = p.palette().index(RED)
    assert c.replace_colour(slot, (0, 255, 0))
    assert (0, 255, 0) in [px for im in e.clipboard["layers"].values() for px in im.get_flattened_data()]


def test_select_options_buttons_follow_the_state(win):
    from src.app.edit_panel import EditPanel
    c, e = win.controller, win.controller.edit
    panel = win.findChild(EditPanel)
    e.set_tool("select")
    b = panel.select_btns
    assert b["select_all"].isEnabled() and not b["copy"].isEnabled() and not b["paste"].isEnabled()
    select(e, (0, 0), (2, 2))
    assert b["copy"].isEnabled() and b["cut"].isEnabled() and b["delete"].isEnabled() and not b["paste"].isEnabled()
    b["copy"].click()
    assert b["paste"].isEnabled()
    b["paste"].click()
    assert e.floating is not None and not b["cut"].isEnabled() and not b["paste"].isEnabled()
    e.escape()
    assert panel.tool_buttons["select"].isEnabled()


def test_a_frame_only_being_looked_at_can_be_selected_and_copied_but_not_cut(win):
    c, e = win.controller, win.controller.edit
    c.select(1)
    select(e, (0, 0), (2, 2))
    assert e.selection == (0, 0, 3, 3) and e.sel_idx == 1 and e.copy() and not e.can_cut
    c.select(0)
    assert e.selection is None                                                  # a selection belongs to one frame
    assert e.paste() and e.fix()


def test_tool_letters_choose_tools_in_edit_mode_only(win, monkeypatch):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    e = win.controller.edit
    monkeypatch.setattr(win, "isActiveWindow", lambda: True)
    monkeypatch.setattr(win, "_text_focus", lambda: False)
    key = lambda k, m=Qt.NoModifier: win._edit_key(QKeyEvent(QEvent.KeyPress, k, m))
    for k, tool in ((Qt.Key_E, "eraser"), (Qt.Key_B, "bucket"), (Qt.Key_S, "select"), (Qt.Key_M, "move"),
                    (Qt.Key_L, "line"), (Qt.Key_R, "square"), (Qt.Key_O, "circle"), (Qt.Key_P, "pencil")):
        assert key(k) and e.tool == tool
    assert not key(Qt.Key_Q) and e.tool == "pencil"
    assert not key(Qt.Key_S, Qt.ControlModifier) and e.tool == "pencil"      # Ctrl+S is not a tool
    e.finish(False)
    ev = QKeyEvent(QEvent.KeyPress, Qt.Key_E, Qt.NoModifier)
    assert not win.eventFilter(win, ev) and e.tool == "pencil"               # outside Edit mode nothing happens
