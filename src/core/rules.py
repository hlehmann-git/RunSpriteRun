"""Name rules shared by project names, frame labels and group names."""
from __future__ import annotations

import re

_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")

MAX_FRAMES = 120
MAX_GROUPS = 32
MIN_SIZE, MAX_SIZE = 4, 128
FPS_CHOICES = (3, 6, 12, 24)
DEFAULT_FPS = 12
GAP_MIN, GAP_MAX, DEFAULT_GAP = 0, 16, 4
PROJECT_NAME_MAX = 40
LABEL_MAX = 40
GROUP_NAME_MAX = 20
KEYS = ("W", "A", "S", "D", "1", "2", "3", "4", "5", "6")


def valid_name(text: str, max_len: int) -> bool:
    """Letters, numbers, - and _ only, no spaces, 1..max_len characters."""
    return 1 <= len(text) <= max_len and _NAME_RE.match(text) is not None


def valid_project_name(text: str) -> bool:
    return valid_name(text, PROJECT_NAME_MAX)


def valid_label(text: str) -> bool:
    return valid_name(text, LABEL_MAX)


def valid_group_name(text: str) -> bool:
    return valid_name(text, GROUP_NAME_MAX)


def copy_label(label: str, existing: set[str]) -> str:
    """Label for a copied frame: the original label with _001 added; _002, _003 ... when that is taken."""
    taken = {e.lower() for e in existing}
    n = 1
    while True:
        suffix = f"_{n:03d}"
        cand = label[: LABEL_MAX - len(suffix)] + suffix
        if cand.lower() not in taken:
            return cand
        n += 1


def default_label(file_stem: str, existing: set[str]) -> str:
    """FR-3.2: file name without extension, disallowed characters become '_'.
    A duplicate gets a three-digit number added (001, 002, ...)."""
    base = re.sub(r"[^A-Za-z0-9_-]", "_", file_stem)[:LABEL_MAX] or "_"
    taken = {e.lower() for e in existing}
    if base.lower() not in taken:
        return base
    n = 1
    while True:
        suffix = f"{n:03d}"
        cand = base[: LABEL_MAX - len(suffix)] + suffix
        if cand.lower() not in taken:
            return cand
        n += 1
