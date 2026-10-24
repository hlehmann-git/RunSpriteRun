"""Save writes the whole project into its project folder (FR-4.4): the .rsr file, the frame PNGs, the all-frames
sheet and the group sheets, with their frame data files. Files written by an earlier Save that are no longer
needed are deleted; nothing else is."""
from __future__ import annotations

import shutil
from pathlib import Path

from src.core.project import Project
from src.io import export
from src.io.project_file import save_project


def save_whole(project: Project, rsr_path: str | Path) -> None:
    """Raises OSError if anything cannot be written. The .rsr is written last, so it always lists the files
    that really exist."""
    if len(project.palette()) > project.system.max_colours:      # such a file could never be opened again
        raise OSError(f"The project uses {len(project.palette())} colours but {project.system.name} allows "
                      f"{project.system.max_colours}. Delete or merge colours first.")
    folder = Path(rsr_path).parent
    old = list(project.written_files)
    if project.source_sheet:                       # the imported sheet is kept in the project folder (FR-1.5)
        src = Path(project.source_sheet)
        dest = folder / src.name
        if src.is_file() and not dest.exists():
            folder.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        project.source_sheet = None
    written = export.write_all(project, folder, project.transparent, with_data=True)
    project.written_files = written
    try:
        save_project(project, rsr_path)
    except BaseException:
        project.written_files = old
        raise
    export.remove_stale(folder, old, written)
