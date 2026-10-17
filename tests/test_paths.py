import re
import sys
from pathlib import Path

from src.io import paths


def _frozen(monkeypatch, tmp_path):
    exe = tmp_path / "Programs" / "RunSpriteRun" / "RunSpriteRun.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    monkeypatch.delenv("RUNSPRITERUN_HOME", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    return exe


def test_installed_work_folders_sit_beside_the_program(monkeypatch, tmp_path):
    exe = _frozen(monkeypatch, tmp_path)
    assert paths.home_folder() == exe.parent
    assert paths.projects_folder() == exe.parent / "Projects" and (exe.parent / "Projects").is_dir()
    assert paths.exports_folder() == exe.parent / "Exports"
    assert paths.blank_sheets_folder() == exe.parent / "Blank sprite sheets"
    assert not (exe.parent / ".rsr_write_test").exists()               # the write test leaves nothing behind


def test_protected_install_folder_falls_back_to_documents(monkeypatch, tmp_path):
    exe = _frozen(monkeypatch, tmp_path)
    monkeypatch.setattr(paths, "_writable", lambda folder: folder != exe.parent)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "user"))
    home = paths.home_folder()
    assert home == tmp_path / "user" / "Documents" / "RunSpriteRun" and home.is_dir()
    assert paths.projects_folder() == home / "Projects"


def test_environment_override_and_source_run(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNSPRITERUN_HOME", str(tmp_path))
    assert paths.home_folder() == tmp_path
    monkeypatch.delenv("RUNSPRITERUN_HOME")
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert (paths.home_folder() / "main.py").exists()                  # running from source: the project folder


def test_version_is_one_number_shown_in_about():
    from src.version import VERSION
    assert re.fullmatch(r"\d+\.\d+\.\d+", VERSION)
    from src.app import info_dialogs
    assert info_dialogs.VERSION == VERSION
