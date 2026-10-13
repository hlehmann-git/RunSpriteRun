"""Small helpers shared by several panels."""
from __future__ import annotations


def frame_choice_text(index: int, label: str) -> str:
    """How a frame is listed in a drop-down: its number and label (FR-3.11)."""
    return f"Frame {index + 1} - {label}"
