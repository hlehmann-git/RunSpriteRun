import pytest
from src.core.colour import (channel_values, is_valid_colour, level_to_8bit, parse_hex,
                             snap_colour, to_hex, to_level)
from src.core.systems import SYSTEMS, get_system


def test_prd_value_tables():
    assert channel_values(2) == [0, 85, 170, 255]
    assert channel_values(3) == [0, 36, 73, 109, 146, 182, 219, 255]
    assert channel_values(4) == [i * 17 for i in range(16)]
    assert len(channel_values(5)) == 32 and channel_values(5)[-1] == 255


@pytest.mark.parametrize("bits", [2, 3, 4, 5])
def test_roundtrip_and_snapping(bits):
    for level in range(1 << bits):
        assert to_level(level_to_8bit(level, bits), bits) == level
    for v in range(256):
        snapped = level_to_8bit(to_level(v, bits), bits)
        # nearest valid value: no other level value is closer
        assert all(abs(snapped - v) <= abs(x - v) for x in channel_values(bits))


def test_snap_colour_and_valid():
    assert snap_colour((100, 200, 10), 3) == (109, 182, 0)
    assert is_valid_colour((109, 182, 0), 3)
    assert not is_valid_colour((100, 200, 10), 3)


def test_hex():
    assert to_hex((0, 146, 255)) == "#0092FF"
    assert parse_hex("0092ff") == (0, 146, 255)
    assert parse_hex("#0092FF") == (0, 146, 255)
    assert parse_hex("#0092F") is None and parse_hex("zzzzzz") is None


def test_system_table():
    assert [s.total_colours for s in SYSTEMS] == [64, 512, 32768, 512, 4096, 4096, 16, 16, 4096]
    assert all(s.total_colours == s.levels ** 3 for s in SYSTEMS if not s.is_fixed)
    assert get_system("Amiga").max_colours == 32
