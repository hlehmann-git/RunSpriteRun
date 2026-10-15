import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image

from src.app.render import fit_scale, render_sprite, render_sprite_at, scaled_sprite


def test_fit_scale_examples_from_prd():
    assert fit_scale(64, 64, 256, 256) == 4
    assert fit_scale(32, 32, 256, 256) == 8
    assert fit_scale(16, 16, 256, 256) == 16
    assert fit_scale(4, 4, 256, 256) == 64
    assert fit_scale(14, 48, 256, 256) == 5            # PRD example: stops at 5x
    assert fit_scale(64, 64, 320, 320) == 5            # 125% display scaling, physical pixels


def test_render_centred_on_black_and_transparent_shown():
    img = Image.new("RGB", (16, 16), (255, 0, 0))
    img.putpixel((0, 0), (0, 146, 255))               # the transparent colour
    out = render_sprite(img, (0, 146, 255), 256, 256, grid=False)
    assert out.size == (256, 256) and out.getpixel((0, 0)) == (0, 146, 255)
    assert out.getpixel((128, 128)) == (255, 0, 0)
    assert out.getpixel((1, 1)) == (0, 146, 255)      # the transparent colour is shown as itself (marks the frame size)
    hidden = scaled_sprite(img, (0, 146, 255), 256, 256, grid=False, hide=True)
    assert hidden.getpixel((1, 1)) == (0, 0, 0)       # timeline boxes still hide it


def test_grid_uses_last_row_and_column_of_each_cell():
    img = Image.new("RGB", (16, 16), (255, 255, 255))
    big = scaled_sprite(img, (1, 2, 3), 256, 256, grid=True)
    s = 16
    assert big.size == (256, 256)
    assert big.getpixel((s - 1, 5)) == (0, 0, 0) and big.getpixel((s - 2, 5)) == (255, 255, 255)
    assert big.getpixel((5, s - 1)) == (0, 0, 0) and big.getpixel((0, 0)) == (255, 255, 255)
    assert big.getpixel((255, 255)) == (0, 0, 0)       # the last cell is closed too


def test_no_grid_at_scale_one_and_exact_pixels():
    img = Image.new("RGB", (4, 4), (10, 20, 30))
    big = scaled_sprite(img, (0, 0, 0), 4, 4, grid=True)
    assert big.size == (4, 4) and big.getpixel((3, 3)) == (10, 20, 30)


def test_zoomed_out_sprite_sits_on_black_with_its_transparent_area_visible():
    img = Image.new("RGB", (10, 10), (0, 146, 255))
    img.putpixel((5, 5), (255, 0, 0))
    out = render_sprite_at(img, (0, 146, 255), 256, 256, 2)       # a 20 px sprite in the middle of a 256 px view
    assert out.getpixel((2, 2)) == (0, 0, 0)                       # the view around the sprite is black
    assert out.getpixel((120, 120)) == (0, 146, 255)               # the sprite's transparent area shows as its colour
