"""Name rules shared by project names, frame labels and group names."""
from __future__ import annotations

import re

_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")

MAX_FRAMES = 120
MAX_GROUPS = 32
MIN_SIZE, MAX_SIZE = 4, 128
FPS_CHOICES = (3, 6, 12, 24)
DEFAULT_FPS = 12
PROJECT_NAME_MAX = 40
NAME_MAX = 60
LABEL_MAX = 64          # name + _ + three digits
GROUP_NAME_MAX = 20
DIAGONALS = {"W+A": ("W", "A"), "W+D": ("W", "D"), "S+D": ("S", "D"), "S+A": ("S", "A")}   # two direction keys held together
KEY_LABELS = {"W+A": "W+A (up-left)", "W+D": "W+D (up-right)", "S+D": "S+D (down-right)", "S+A": "S+A (down-left)"}
KEYS = ("W", "A", "S", "D", "W+A", "W+D", "S+D", "S+A", "1", "2", "3", "4", "5", "6")


def valid_name(text: str, max_len: int) -> bool:
    """Letters, numbers, - and _ only, no spaces, 1..max_len characters."""
    return 1 <= len(text) <= max_len and _NAME_RE.match(text) is not None


def valid_project_name(text: str) -> bool:
    return valid_name(text, PROJECT_NAME_MAX)


def valid_label(text: str) -> bool:
    return valid_name(text, LABEL_MAX)


def valid_group_name(text: str) -> bool:
    return valid_name(text, GROUP_NAME_MAX)


_NUM_SUFFIX = re.compile(r"_(\d{3})$")
_OLD_NUM = re.compile(r"_\d+$")


def clean_name(text: str) -> str:
    """A frame name from any text: disallowed characters become '_', at most NAME_MAX characters, never empty."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", text)[:NAME_MAX] or "Frame"


def valid_frame_name(text: str) -> bool:
    return valid_name(text, NAME_MAX)


def name_of(label: str) -> str:
    """The name part of a label: the label without its final _NNN (three digits)."""
    m = _NUM_SUFFIX.search(label)
    return label[: m.start()] if m else label


def make_label(name: str, number: int) -> str:
    return f"{name}_{number:03d}"


def old_label_name(label: str) -> str:
    """Name for a label from an older project: the label without a trailing _number."""
    return clean_name(_OLD_NUM.sub("", label))


def default_label(file_stem: str) -> str:
    """The name for a frame imported from a file or sheet: its name, disallowed characters become '_'."""
    return clean_name(file_stem)
