import json
import zipfile

import pytest
from PIL import Image

from src.core.factory import create_project
from src.core.importer import import_files
from src.core.project import Group, Rule
from src.core.systems import get_system
from src.io.project_file import ProjectFileError, open_project, save_project
from tests.helpers import make_png

GENESIS = get_system("Sega Genesis / Mega Drive")


@pytest.fixture
def project(tmp_path):
    a = make_png(tmp_path / "a.png", colours=((255, 0, 0), (0, 0, 0)))
    b = make_png(tmp_path / "b.png", colours=((0, 0, 255),))
    proj = create_project("Demo", GENESIS, 8, 8, import_files([a, b], GENESIS, 8, 8), fps=24)
    proj.groups = [Group("Walk", 0, 1, key="D", on_release=Rule("group", "Walk", True), colour=(10, 20, 30))]
    proj.start_state = Rule("frame", "a")
    return proj


def test_roundtrip(project, tmp_path):
    f = tmp_path / "Demo.rsr"
    save_project(project, f)
    back = open_project(f)
    assert (back.name, back.system.name, back.width, back.height, back.fps) == ("Demo", GENESIS.name, 8, 8, 24)
    assert back.transparent == project.transparent
    assert [x.label for x in back.frames] == ["a_001", "b_002"]       # numbered by position on opening
    assert all(x.image.tobytes() == y.image.tobytes() for x, y in zip(back.frames, project.frames))
    assert back.groups == project.groups and back.start_state == project.start_state


def _rewrite(src, dst, edit):
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, "w") as zo:
        for n in zi.namelist():
            data = zi.read(n)
            data = edit(n, data)
            if data is not None:
                zo.writestr(n, data)


def test_unknown_fields_tolerated(project, tmp_path):
    f, g = tmp_path / "a.rsr", tmp_path / "b.rsr"
    save_project(project, f)

    def add(n, d):
        if n == "project.json":
            m = json.loads(d)
            m["future_field"] = {"x": 1}
            return json.dumps(m)
        return d
    _rewrite(f, g, add)
    assert open_project(g).name == "Demo"


@pytest.mark.parametrize("what", ["not_zip", "no_json", "bad_version", "missing_frame", "wrong_size", "bad_colour", "bad_name"])
def test_damaged_files_never_open_partly(project, tmp_path, what):
    f, g = tmp_path / "a.rsr", tmp_path / "bad.rsr"
    save_project(project, f)
    if what == "not_zip":
        g.write_bytes(b"hello")
    elif what == "no_json":
        _rewrite(f, g, lambda n, d: None if n == "project.json" else d)
    elif what == "missing_frame":
        _rewrite(f, g, lambda n, d: None if n == "frames/002.png" else d)
    elif what == "wrong_size":
        def e(n, d):
            if n == "frames/001.png":
                import io
                buf = io.BytesIO(); Image.new("RGB", (9, 8)).save(buf, "PNG"); return buf.getvalue()
            return d
        _rewrite(f, g, e)
    elif what == "bad_colour":
        def e(n, d):
            if n == "frames/001.png":
                import io
                buf = io.BytesIO(); Image.new("RGB", (8, 8), (100, 100, 100)).save(buf, "PNG"); return buf.getvalue()
            return d
        _rewrite(f, g, e)
    else:
        def e(n, d):
            if n != "project.json":
                return d
            m = json.loads(d)
            m["format_version" if what == "bad_version" else "name"] = 99 if what == "bad_version" else "bad name"
            return json.dumps(m)
        _rewrite(f, g, e)
    with pytest.raises(ProjectFileError):
        open_project(g)


def test_missing_file(tmp_path):
    with pytest.raises(ProjectFileError):
        open_project(tmp_path / "nope.rsr")


def test_failed_save_leaves_old_file(project, tmp_path):
    f = tmp_path / "Demo.rsr"
    save_project(project, f)
    before = f.read_bytes()
    project.frames[0].image = None          # makes saving blow up part-way
    with pytest.raises(Exception):
        save_project(project, f)
    assert f.read_bytes() == before and [p.name for p in tmp_path.iterdir() if p.suffix == ".tmp"] == []


def test_old_file_labels_are_converted(project, tmp_path):
    f, g = tmp_path / "Demo.rsr", tmp_path / "Old.rsr"
    save_project(project, f)

    def drop_flag(n, d):
        if n != "project.json":
            return d
        meta = json.loads(d)
        meta.pop("labels", None)
        meta["frames"][0]["label"] = "Idle_4"
        meta["frames"][1]["label"] = "Run"
        meta["start_state"] = {"kind": "frame", "target": "Idle_4", "loop": False}
        return json.dumps(meta)
    _rewrite(f, g, drop_flag)
    back = open_project(g)
    assert [x.label for x in back.frames] == ["Idle_001", "Run_002"] and back.start_state.target == "Idle_001"
    assert not back.dirty
    save_project(back, f)
    assert [x.label for x in open_project(f).frames] == ["Idle_001", "Run_002"]
