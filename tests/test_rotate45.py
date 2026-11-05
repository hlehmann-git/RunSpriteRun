"""v2.0.20: rotate by 45 degrees with RotSprite (core), and the Action row's two rotate buttons (which took the place
of Undo and Redo) in the editor."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image, ImageDraw
from PySide6.QtWidgets import QApplication

from src.app.edit_panel import EditPanel
from src.app.main_window import MainWindow
from src.core import layers as L, rotsprite
from src.core.project import Frame, Project
from src.core.systems import get_system

T = (0, 0, 0)
RED, BLUE = (255, 0, 0), (0, 0, 255)


def colours(img):
    return {c for _n, c in img.getcolors(img.width * img.height)}


def sprite(w=20, h=14):
    im = Image.new("RGB", (w, h), T)
    d = ImageDraw.Draw(im)
    d.rectangle([3, 3, w - 6, h - 5], fill=RED)
    d.line([0, 0, w - 1, h - 1], fill=BLUE)
    return im


# ---- the RotSprite core ---------------------------------------------------------------------------------
def test_rotsprite_never_makes_new_colours():
    im = sprite()
    for angle in (45, -45, 135, 225):
        assert colours(rotsprite.rotate(im, angle, T)) <= colours(im)


def test_quarter_turns_are_exact_and_negative_angles_wrap():
    im = sprite()
    assert rotsprite.rotate(im, 90, T).tobytes() == im.transpose(Image.ROTATE_270).tobytes()
    assert rotsprite.rotate(im, -90, T).tobytes() == im.transpose(Image.ROTATE_90).tobytes()
    assert rotsprite.rotate(im, 180, T).tobytes() == im.transpose(Image.ROTATE_180).tobytes()
    assert rotsprite.rotate(im, 360, T).tobytes() == im.tobytes()
    assert rotsprite.rotate(im, -45, T).tobytes() == rotsprite.rotate(im, 315, T).tobytes()


def test_a_45_degree_turn_is_bigger_and_only_steps_of_45_are_allowed():
    im = sprite(16, 16)
    out = rotsprite.rotate(im, 45, T)
    assert out.width > 16 and out.height > 16
    with pytest.raises(ValueError):
        rotsprite.rotate(im, 30, T)


def test_clockwise_moves_the_top_towards_the_right():
    im = Image.new("RGB", (15, 15), T)
    ImageDraw.Draw(im).rectangle([6, 0, 8, 4], fill=RED)            # a bar at the top middle
    out = rotsprite.rotate(im, 45, T)
    box = L.opaque_mask(out, T).getbbox()
    assert box[0] > out.width // 2 and box[3] <= out.height // 2   # now top right


def test_is_blank():
    assert rotsprite.is_blank(Image.new("RGB", (4, 4), T), T)
    assert not rotsprite.is_blank(sprite(), T)


# ---- the editor -----------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def project(w=16, h=16, img=None):
    if img is None:
        img = Image.new("RGB", (w, h), T)
        ImageDraw.Draw(img).rectangle([5, 2, 9, 11], fill=RED)
    return Project(name="Rot", system=get_system("Sega Genesis / Mega Drive"), width=img.width, height=img.height,
                   transparent=T, frames=[Frame("F1", img.copy()), Frame("F2", img.copy())])


def start(app, p):
    w = MainWindow()
    w.set_project(p)
    assert w.controller.edit.begin()
    return w


@pytest.fixture
def win(app):
    return start(app, project())


def frame(w, i=0):
    return w.controller.project.frames[i].image


def test_the_buttons_replace_undo_and_redo_with_the_same_icons(win):
    panel = win.findChild(EditPanel)
    a = panel.actions
    assert list(a)[-2:] == ["rotate_ccw45", "rotate_cw45"]
    assert a["rotate_ccw45"].kind == "undo" and a["rotate_cw45"].kind == "redo"        # the circular arrows
    assert "45 degrees left" in a["rotate_ccw45"].toolTip() and "45 degrees right" in a["rotate_cw45"].toolTip()
    assert a["rotate_ccw45"].isEnabled() and a["rotate_cw45"].isEnabled()
    win.controller.edit.finish(False)
    assert not a["rotate_cw45"].isEnabled()


def test_rotating_floats_and_esc_puts_everything_back(win):
    e = win.controller.edit
    before = frame(win).tobytes()
    panel = win.findChild(EditPanel)
    panel.actions["rotate_cw45"].click()
    assert e.floating is not None and "rot" in e.floating
    assert win.panels["Frame view"].edit_note.text() == "ROTATING"
    assert panel.hint.fontMetrics().horizontalAdvance(e.rotate_message()) <= panel.hint.width()   # fits the head
    assert frame(win).tobytes() != before
    assert e.escape()
    assert e.floating is None and frame(win).tobytes() == before and not e.can_undo


def test_enter_fixes_it_as_one_undo_step(win):
    e = win.controller.edit
    before = frame(win).tobytes()
    assert e.rotate45(True) and e.fix()
    assert e.floating is None and frame(win).tobytes() != before
    assert colours(frame(win)) <= {T, RED}                      # no new colours
    assert e.undo() and frame(win).tobytes() == before and not e.can_undo


def test_two_clicks_give_the_exact_90_degree_turn(win):
    e = win.controller.edit
    original = frame(win).copy()
    assert e.rotate45(True) and e.rotate45(True) and e.fix()
    assert frame(win).tobytes() == original.transpose(Image.ROTATE_270).tobytes()


def test_left_then_right_lands_back_on_the_same_pixels(win):
    e = win.controller.edit
    before = frame(win).tobytes()
    for cw in (False, False, False, True, True, True):            # goes through 45, 90 and 135 sizes and back
        assert e.rotate45(cw)
    assert e.floating["rot"]["angle"] == 0 and frame(win).tobytes() == before


def test_it_keeps_turning_from_the_original_not_from_the_last_result(win):
    e = win.controller.edit
    src = frame(win).copy()
    for _ in range(3):
        assert e.rotate45(True)
    assert e.floating["rot"]["angle"] == 135
    one_turn = rotsprite.rotate(src, 135, T)
    assert e.floating["clips"][L.CORE].tobytes() == one_turn.tobytes()


def test_ctrl_z_while_it_floats_cancels_it(win):
    e = win.controller.edit
    before = frame(win).tobytes()
    assert e.rotate45(False)
    win.act_undo.trigger()
    assert e.floating is None and frame(win).tobytes() == before


def test_a_selection_turns_only_its_own_pixels(app):
    img = Image.new("RGB", (24, 16), T)
    d = ImageDraw.Draw(img)
    d.rectangle([2, 4, 7, 11], fill=RED)                          # inside the selection
    d.rectangle([18, 2, 21, 13], fill=BLUE)                       # outside it
    w = start(app, project(img=img))
    e = w.controller.edit
    e.set_tool("select")
    assert e.press((0, 0))
    e.move((11, 15))
    e.release((11, 15))
    assert e.rotate45(True) and e.fix()
    out = frame(w)
    assert out.crop((14, 0, 24, 16)).tobytes() == img.crop((14, 0, 24, 16)).tobytes()   # untouched
    assert out.crop((0, 0, 12, 16)).tobytes() != img.crop((0, 0, 12, 16)).tobytes()


def test_each_layer_turns_on_its_own(win):
    e = win.controller.edit
    win.controller.project.extra_colours.append(BLUE)               # blue must be in the palette to draw with it
    e.set_active(BLUE)
    e.set_target(L.CORE, False)
    e.set_target(L.FG, True)
    e.set_option("pencil", "pixel_perfect", False)
    e.set_tool("pencil")
    assert e.press((7, 13))
    e.release((7, 13))                                             # a blue pixel on ForeGround 1
    e.set_target(L.CORE, True)
    assert e.rotate45(True) and e.rotate45(True) and e.fix()
    layers = win.controller.project.frames[0].layers
    assert colours(layers[L.FG]) == {T, BLUE} and colours(layers[L.CORE]) == {T, RED}


def test_only_the_ticked_layers_turn(win):
    e = win.controller.edit
    e.set_target(L.CORE, False)
    e.set_target(L.FG, True)
    assert not e.rotate45(True)                                    # nothing drawn on ForeGround 1
    assert e.floating is None


def test_pixels_pushed_off_the_frame_are_counted_and_cut_off(app):
    img = Image.new("RGB", (16, 16), T)
    img.putpixel((0, 0), RED)                                      # a corner: at 45 degrees it leaves the frame
    ImageDraw.Draw(img).rectangle([6, 6, 9, 9], fill=RED)          # a solid block in the middle stays
    w = start(app, project(img=img))
    e = w.controller.edit
    notices = []
    e.notice.connect(notices.append)
    assert e.rotate45(True)
    assert e.cut_off_pixels() >= 1 and "cut off" in notices[-1] and "45° right" in notices[-1]
    assert e.fix()
    assert colours(frame(w)) == {T, RED}                           # the middle block is kept...
    assert L.opaque_mask(frame(w), T).getbbox()[1] >= 2            # ...and nothing is left at the top edge


def test_nudging_it_back_inside_clears_the_cut_off(app):
    img = Image.new("RGB", (16, 16), T)
    img.putpixel((0, 0), RED)                                      # turned 45 right, it ends up above the frame
    w = start(app, project(img=img))
    e = w.controller.edit
    notices = []
    e.notice.connect(notices.append)
    assert e.rotate45(True) and e.cut_off_pixels() == 1
    for _ in range(4):
        assert e.nudge(0, 1)
    assert e.cut_off_pixels() == 0 and "cut off" not in notices[-1]
    assert e.fix() and colours(frame(w)) == {T, RED}


def test_the_90_degree_buttons_keep_turning_a_floating_rotation_even_on_a_non_square_frame(app):
    w = start(app, project(img=sprite(20, 14)))
    e = w.controller.edit
    a = w.findChild(EditPanel).actions
    assert not a["rotate_right"].isEnabled()                       # 20 x 14: no 90 degree turn on its own
    assert e.rotate45(True)
    assert a["rotate_right"].isEnabled()
    a["rotate_right"].click()
    assert e.floating["rot"]["angle"] == 135


def test_a_flip_while_turning_flips_the_turned_picture(win):
    e = win.controller.edit
    assert e.rotate45(True)
    turned = e.floating["clips"][L.CORE].copy()
    assert e.action("flip_h")
    assert e.floating["clips"][L.CORE].tobytes() == turned.transpose(Image.FLIP_LEFT_RIGHT).tobytes()   # exact
    notices = []
    e.notice.connect(notices.append)
    assert e.rotate45(True)                    # a flipped 45-right picture looks like 45 left; 45 more right as seen
    assert "back to the start" in notices[-1]  # = no turn left, only the flip
    assert e.floating["clips"][L.CORE].tobytes() == e.floating["rot"]["src"][L.CORE].transpose(Image.FLIP_LEFT_RIGHT).tobytes()


def test_after_a_flip_a_clockwise_click_turns_clockwise_as_seen(win):
    e = win.controller.edit
    assert e.select_all()
    e.deselect()
    src = frame(win).copy()
    assert e.action("flip_h")                                       # flip with nothing floating: a plain flip
    flipped = frame(win).copy()
    assert e.rotate45(True) and e.rotate45(True) and e.fix()
    assert frame(win).tobytes() == flipped.transpose(Image.ROTATE_270).tobytes()
    assert src.tobytes() != flipped.tobytes()


def test_flips_while_turning_are_exact_and_flipping_twice_undoes_it(win):
    e = win.controller.edit
    assert e.rotate45(True)
    turned = e.floating["clips"][L.CORE].copy()
    assert e.action("flip_v")
    assert e.floating["clips"][L.CORE].tobytes() == turned.transpose(Image.FLIP_TOP_BOTTOM).tobytes()
    assert e.action("flip_v") and e.action("flip_h") and e.action("flip_h")
    assert e.floating["clips"][L.CORE].tobytes() == turned.tobytes()


def test_a_floating_paste_can_be_turned_too(win):
    e = win.controller.edit
    assert e.select_all() and e.copy()
    e.deselect()
    assert e.paste() and e.rotate45(True)
    assert e.floating["rot"]["angle"] == 45 and e.fix()


def test_only_the_frame_being_edited_can_be_turned(win):
    c, e = win.controller, win.controller.edit
    c.selected = 1
    c.selection_changed.emit(1)
    assert not e.rotate45(True) and e.floating is None
