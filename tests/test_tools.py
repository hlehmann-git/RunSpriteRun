from src.core.tools import (brush, circle_shape, flood, line_points, line_shape, lock_angle, lock_axis, pixel_perfect,
                            rect_shape, stroke)


def test_line_includes_both_ends():
    assert line_points(0, 0, 4, 0) == [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]
    assert line_points(3, 3, 0, 0)[0] == (3, 3) and line_points(3, 3, 0, 0)[-1] == (0, 0)


def test_pixel_perfect_drops_corner_pixels():
    assert pixel_perfect([(0, 0), (1, 0), (1, 1)]) == [(0, 0), (1, 1)]
    assert pixel_perfect([(0, 0), (1, 0), (2, 0)]) == [(0, 0), (1, 0), (2, 0)]


def test_brush_sizes_and_round_shape():
    assert len(brush(5, 5, 1)) == 1 and len(brush(5, 5, 3)) == 9
    assert len(brush(5, 5, 5, "Round")) < 25


def test_shift_locks():
    assert lock_axis((2, 2), (9, 4)) == (9, 2) and lock_axis((2, 2), (4, 9)) == (2, 9)
    assert lock_angle((0, 0), (10, 1)) == (10, 0) and lock_angle((0, 0), (1, 10)) == (0, 10)
    assert lock_angle((0, 0), (8, 6)) == (8, 8) and lock_angle((5, 5), (1, 3)) == (1, 5)
    assert lock_angle((5, 5), (1, 1)) == (1, 1)


def test_shift_makes_a_square_and_a_true_circle():
    sq = rect_shape((2, 2), (9, 5), 1, True, False, True)
    xs, ys = {x for x, _ in sq}, {y for _, y in sq}
    assert max(xs) - min(xs) == max(ys) - min(ys)
    c = circle_shape((2, 2), (11, 5), 1, True, False, True)
    xs, ys = {x for x, _ in c}, {y for _, y in c}
    assert max(xs) - min(xs) == max(ys) - min(ys)


def test_rect_outline_filled_and_from_centre():
    assert len(rect_shape((0, 0), (3, 3), 1, False, False, False)) == 12
    assert len(rect_shape((0, 0), (3, 3), 1, True, False, False)) == 16
    pts = rect_shape((5, 5), (7, 7), 1, True, True, False)
    assert min(pts) == (3, 3) and max(pts) == (7, 7)


def test_flood_contiguous_and_global():
    grid = ["aab", "abb", "aab"]
    get = lambda x, y: grid[y][x]
    assert flood(get, 3, 3, 0, 0, True) == {(0, 0), (1, 0), (0, 1), (0, 2), (1, 2)}
    assert len(flood(get, 3, 3, 2, 0, False)) == 4
    assert flood(get, 3, 3, 9, 9, True) == set()


def test_stroke_connects_mouse_positions():
    assert stroke([(0, 0), (5, 0)], 1, "Square", True) == {(x, 0) for x in range(6)}
