"""Where the app's folders are. The home folder is the folder the program lives in (the project folder while
developing, the folder holding the .exe once packaged). Projects, inside it, is where .rsr files go by default."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def home_folder() -> Path:
    env = os.environ.get("RUNSPRITERUN_HOME")
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def projects_folder() -> Path:
    """The Projects folder inside home. It is created if it is missing; if that is not possible
    (a read-only location) the home folder is used instead."""
    p = home_folder() / "Projects"
    try:
        p.mkdir(exist_ok=True)
    except OSError:
        return home_folder()
    return p


def exports_folder() -> Path:
    """Where Export starts: the Exports folder in the home folder, beside Projects (created when Export runs)."""
    return home_folder() / "Exports"


def project_folder(parent: Path, name: str) -> Path:
    """The folder of a project: <parent>/<name>. The .rsr file is <name>.rsr inside it."""
    return Path(parent) / name


def save_folder(project_file: str | None) -> Path:
    """Where Save As starts: the folder of the project's last save, or Projects."""
    if project_file:
        folder = Path(project_file).parent
        if folder.is_dir():
            return folder
    return projects_folder()


def blank_sheets_folder() -> Path:
    """Where Create Blank Sprite Sheet saves: the Blank sprite sheets folder in the home folder, beside Projects
    and Exports (created when a sheet is made). Each system has its own subfolder."""
    return home_folder() / "Blank sprite sheets"
