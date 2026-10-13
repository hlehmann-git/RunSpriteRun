"""Writing the project's image files (FR-4.4 Save, FR-4.7 Export). Save writes the sheets, the frame PNGs and the
frame data files into the project folder; Export writes the images only into a new export folder."""
from __future__ import annotations

from pathlib import Path

from src.core import sheets
from src.core.colour import Colour
from src.core.project import Project
from src.core.sheets import FOLDER_GROUP_SHEETS, FOLDER_SHEET, FOLDER_SPRITES, FOLDERS


def planned_files(project: Project, with_data: bool) -> list[str]:
    """Relative paths (with /) of every file a write would create."""
    out = [f"{FOLDER_SHEET}/{sheets.all_sheet_name(project)}"]
    if with_data:
        out.append(f"{FOLDER_SHEET}/{sheets.all_sheet_name(project)[:-4]}.txt")
    for g in project.groups:
        name = sheets.group_sheet_name(project, g.name)
        out.append(f"{FOLDER_GROUP_SHEETS}/{name}")
        if with_data:
            out.append(f"{FOLDER_GROUP_SHEETS}/{name[:-4]}.txt")
    out += [f"{FOLDER_SPRITES}/{sheets.frame_file_name(project, i)}" for i in range(len(project.frames))]
    return out


def sheet_count(project: Project) -> int:
    return 1 + len(project.groups)


def largest_sheet(project: Project, gap: int) -> tuple[int, int]:
    """Size of the biggest sheet that a write would make (for the Export window summary)."""
    colours = len(project.palette())
    sizes = [sheets.sheet_size(len(project.frames), project.width, project.height, gap, colours)]
    for g in project.groups:
        sizes.append(sheets.sheet_size(g.last - g.first + 1, project.width, project.height, gap, colours))
    return max(sizes, key=lambda s: s[0] * s[1])


def write_all(project: Project, folder: Path, gap: int, fill: Colour, with_data: bool) -> list[str]:
    """Write every sheet, every frame PNG and (when asked) the frame data files under `folder`. The three folders
    are created even when nothing goes in one. Returns the relative paths written. Raises OSError."""
    folder = Path(folder)
    for name in FOLDERS:
        (folder / name).mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    def put_sheet(rel_folder: str, file_name: str, indices: list[int]) -> None:
        sheet = sheets.build_sheet(project, indices, gap, fill)
        sheet.image.save(folder / rel_folder / file_name, format="PNG")
        written.append(f"{rel_folder}/{file_name}")
        if with_data:
            data_name = file_name[:-4] + ".txt"
            text = sheets.frame_data_text(project, file_name, sheet.image.size, sheet.positions)
            (folder / rel_folder / data_name).write_text(text, encoding="utf-8", newline="\n")
            written.append(f"{rel_folder}/{data_name}")

    put_sheet(FOLDER_SHEET, sheets.all_sheet_name(project), list(range(len(project.frames))))
    for g in project.groups:
        put_sheet(FOLDER_GROUP_SHEETS, sheets.group_sheet_name(project, g.name), list(range(g.first, g.last + 1)))
    for i, frame in enumerate(project.frames):
        name = sheets.frame_file_name(project, i)
        frame.image.save(folder / FOLDER_SPRITES / name, format="PNG")
        written.append(f"{FOLDER_SPRITES}/{name}")
    return written


def clean_written_list(items) -> list[str]:
    """The list stored in the .rsr is used to delete files, so only plain relative paths inside the three
    folders are accepted; anything else is dropped."""
    out: list[str] = []
    if not isinstance(items, list):
        return out
    for rel in items:
        if not isinstance(rel, str) or "\\" in rel or rel.startswith("/") or ":" in rel:
            continue
        parts = rel.split("/")
        if len(parts) != 2 or parts[0] not in FOLDERS or parts[1] in ("", ".", ".."):
            continue
        out.append(rel)
    return out


def remove_stale(folder: Path, old: list[str], new: list[str]) -> None:
    """Delete files Save wrote last time that this Save did not write again. Anything not on the old list is
    never touched. Problems deleting a file are ignored (the file stays)."""
    folder = Path(folder)
    keep = set(new)
    for rel in clean_written_list(old):
        if rel in keep:
            continue
        path = folder / rel
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            pass


def inside_project_folder(parent: Path, project: Project) -> bool:
    """True if `parent` is a project folder or inside one (Export refuses these, FR-4.7). A project folder is the
    folder of the open project's .rsr file, or any folder that holds a <foldername>.rsr file."""
    try:
        here = Path(parent).resolve()
    except OSError:
        here = Path(parent)
    own = Path(project.file_path).resolve().parent if project.file_path else None
    for p in (here, *here.parents):
        if own is not None and p == own:
            return True
        if (p / f"{p.name}.rsr").is_file():
            return True
    return False


def existing_files(folder: Path, files: list[str]) -> list[str]:
    return [rel for rel in files if (Path(folder) / rel).exists()]
