"""The eyedropper icon: 24 x 24 pixel art drawn from a few shapes, light from the top left. The liquid
takes the colour given, with a flat top. Returned as a dict {(x, y): (r, g, b)}."""
from __future__ import annotations

import math
from functools import lru_cache

SIZE = 24
LIQUID_TOP = 0.72                 # the liquid surface: everything below this line is liquid (flat top)


def _mix(c, k):
    return tuple(max(0, min(255, int(v * k if k <= 1 else v + (255 - v) * (k - 1)))) for v in c)


@lru_cache(maxsize=64)
def eyedropper(liquid: tuple[int, int, int]) -> dict[tuple[int, int], tuple[int, int, int]]:
    n = SIZE
    glass, glass_hi, glass_lo = (232, 236, 245), (255, 255, 255), (150, 158, 182)
    rubber, rubber_hi, rubber_lo = (40, 96, 200), (96, 156, 245), (22, 52, 128)     # the handle is blue
    edge = 1.3 / n
    px: dict[tuple[int, int], tuple[int, int, int]] = {}
    for y in range(n):
        for x in range(n):
            X, Y = (x + .5) / n, (y + .5) / n
            t = (X + 1 - Y) / math.sqrt(2)             # along the dropper, tip (0) to bulb end
            d = (X + Y - 1) / math.sqrt(2)             # across it; negative is the upper-left side
            if 0.14 <= t < 0.34:
                part, hw = "tube", 0.03 + (t - 0.14) / 0.20 * (0.115 - 0.03)
            elif 0.34 <= t < 0.84:
                part, hw = "tube", 0.115
            elif 0.84 <= t < 0.92:
                part, hw = "collar", 0.165
            elif 0.92 <= t <= 1.28:
                part, hw = "bulb", 0.145
                if t > 1.10:
                    hw *= math.sqrt(max(0.0, 1 - ((t - 1.10) / 0.18) ** 2))
            else:
                continue
            if abs(d) > hw:
                continue
            hi, lo = d < -(hw - edge), d > (hw - edge)
            if part == "tube":
                if Y >= LIQUID_TOP and t < 0.80:
                    surface = Y < LIQUID_TOP + 1.0 / n
                    c = _mix(liquid, 1.5) if (hi or surface) else _mix(liquid, 0.6) if lo else liquid
                else:
                    c = glass_hi if hi else glass_lo if lo else glass
            else:
                c = rubber_hi if hi else rubber_lo if lo else rubber
                if part == "bulb" and not hi and not lo and 1.0 < t < 1.08 and -0.07 < d < -0.02:
                    c = rubber_hi                         # small highlight on the bulb
            px[(x, y)] = c
    black = (0, 0, 0)
    for (x, y) in list(px):                                # 1 px black outline
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (x + dx, y + dy)
            if q not in px and 0 <= q[0] < n and 0 <= q[1] < n:
                px[q] = black
    return px
