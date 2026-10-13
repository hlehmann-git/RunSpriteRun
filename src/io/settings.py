"""Settings file (FR-5.3): a small JSON file in the user's Windows application data folder, not in project
files. A missing or damaged file means the defaults; one bad value falls back to its own default."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

EXPORT_MODES = ("sheet", "groups")            # One sheet with all frames / One sheet per Frame Group
GAP_MIN, GAP_MAX, GAP_DEFAULT = 0, 16, 4


@dataclass
class Settings:
    grid: bool = True                          # pixel grid in the Frame view (default on)
    gap: int = GAP_DEFAULT                     # sprite sheet gap in pixels
    export_mode: str = "sheet"                 # what the Export Sprite Sheet dialog starts with


def settings_path() -> Path:
    env = os.environ.get("RUNSPRITERUN_SETTINGS")
    if env:
        return Path(env)
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / ".config"
    return root / "RunSpriteRun" / "settings.json"


def load(path: Path | None = None) -> Settings:
    s = Settings()
    try:
        data = json.loads((path or settings_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return s
    if not isinstance(data, dict):
        return s
    if isinstance(data.get("grid"), bool):
        s.grid = data["grid"]
    gap = data.get("gap")
    if isinstance(gap, int) and not isinstance(gap, bool) and GAP_MIN <= gap <= GAP_MAX:
        s.gap = gap
    if data.get("export_mode") in EXPORT_MODES:
        s.export_mode = data["export_mode"]
    return s


def save(settings: Settings, path: Path | None = None) -> bool:
    """Returns False if the file could not be written (settings then last only for this run)."""
    p = path or settings_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
        return True
    except OSError:
        return False
