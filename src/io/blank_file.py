"""Writing a blank sprite sheet picture into the Blank sprite sheets folder (FR-4.9)."""
from __future__ import annotations

from pathlib import Path

from src.core import blank_sheet
from src.core.colour import Colour
from src.core.systems import System
from src.io import paths


def target_path(system: System, w: int, h: int, per_row: int, rows: int, base: Path | None = None) -> Path:
    base = Path(base) if base is not None else paths.blank_sheets_folder()
    return base / blank_sheet.system_folder(system) / blank_sheet.file_name(system, w, h, per_row, rows)


def write(system: System, w: int, h: int, per_row: int, rows: int, box: Colour, fill: Colour,
          base: Path | None = None) -> Path:
    """Make the sheet and save it as a 24-bit PNG. The system's folder is created when missing. Raises OSError."""
    path = target_path(system, w, h, per_row, rows, base)
    path.parent.mkdir(parents=True, exist_ok=True)
    blank_sheet.build(system, w, h, per_row, rows, box, fill).save(path, format="PNG")
    return path
