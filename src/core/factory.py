"""Build a Project from a successful import (section 5.3 Behaviour)."""
from __future__ import annotations

from .importer import ImportResult
from .project import Frame, Project
from .rules import DEFAULT_FPS, FPS_CHOICES, valid_project_name
from .systems import System


class CreateProjectError(ValueError):
    pass


def create_project(name: str, system: System, width: int, height: int,
                   result: ImportResult, fps: int = DEFAULT_FPS) -> Project:
    if not valid_project_name(name):
        raise CreateProjectError("Invalid project name.")
    if fps not in FPS_CHOICES:
        raise CreateProjectError("Invalid frames per second.")
    if not result.can_create:
        raise CreateProjectError("The import is not ready to create a project.")
    project = Project(
        name=name, system=system, width=width, height=height, fps=fps,
        transparent=result.transparent_default,
        frames=[Frame(f.label, f.image) for f in result.frames],
    )
    from .edit import renumber
    renumber(project)                       # labels are name_NNN, the number being the frame's position
    return project
