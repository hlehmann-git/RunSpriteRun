import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from src.app import messages, start_project
from src.app.start_project import StartProjectDialog
from src.core.importer import msg_frame_limit
from src.io.project_file import save_project
from tests.helpers import make_png


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def shown(monkeypatch):
    """Collect the messages instead of showing real boxes."""
    log = {"warn": [], "choose": [], "adjusted": []}
    monkeypatch.setattr(messages, "warn", lambda p, text, detail=None: log["warn"].append((text, detail)))
    monkeypatch.setattr(messages, "adjusted", lambda p, lines, details: log["adjusted"].append(lines))
    log["answer"] = True
    monkeypatch.setattr(messages, "choose", lambda p, t, d, y, n: (log["choose"].append((t, d)), log["answer"])[1])
    return log


def test_defaults_and_system_details(app, tmp_path):
    d = StartProjectDialog(folder=str(tmp_path))
    assert d.system.currentText() == "Atari ST"
    assert d.fps.currentText() == "12" and d.from_files.isChecked()
    assert d._detail_values["Total palette colours"].text() == "512"
    d.system.setCurrentText("Amiga")
    assert d._detail_values["Max sprite colours"].text() == "32"
    assert d._detail_values["Total palette colours"].text() == "4,096"
    assert not d.create_btn.isEnabled()


def test_create_enabled_rules_and_name_error(app, tmp_path):
    d = StartProjectDialog(folder=str(tmp_path))
    d.set_files([make_png(tmp_path / "a.png")])
    d.name.setText("bad name")
    assert not d.create_btn.isEnabled() and "no spaces" in d.name_hint.text()
    d.name.setText("Demo_1")
    assert d.create_btn.isEnabled()


def test_size_read_from_files_and_natural_order(app, tmp_path):
    d = StartProjectDialog(folder=str(tmp_path))
    d.set_files([make_png(tmp_path / n, size=(16, 12)) for n in ("f10.png", "f2.png", "f1.png")])
    assert [d.file_list.item(i).text() for i in range(3)] == ["f1.png", "f2.png", "f10.png"]
    assert (d.width_box.value(), d.height_box.value()) == (16, 12)
    assert d.summary.text() == "3 files selected, all 16 x 12"
    assert not d.width_box.isEnabled()
    d.from_files.setChecked(False)
    assert d.width_box.isEnabled()


def test_create_project_success(app, tmp_path, shown):
    d = StartProjectDialog(folder=str(tmp_path))
    d.set_files([make_png(tmp_path / "a.png", colours=((255, 0, 0), (0, 0, 0))),
                 make_png(tmp_path / "b.png", colours=((0, 0, 255),))])
    d.name.setText("Demo")
    d.fps.setCurrentText("24")
    d._create()
    p = d.project
    assert p and (p.name, p.fps, p.width, p.height, len(p.frames)) == ("Demo", 24, 8, 8, 2)
    assert p.transparent == (255, 0, 0) and not shown["warn"]


def test_frame_limit_stays_open(app, tmp_path, shown):
    f = make_png(tmp_path / "a.png")
    d = StartProjectDialog(folder=str(tmp_path))
    d.set_files([f] * 121)
    d.name.setText("Demo")
    d._create()
    assert d.project is None and shown["warn"][0][0] == msg_frame_limit(121)


def test_mixed_sizes_block(app, tmp_path, shown):
    d = StartProjectDialog(folder=str(tmp_path))
    d.set_files([make_png(tmp_path / "a.png"), make_png(tmp_path / "b.png", size=(9, 8))])
    d.name.setText("Demo")
    assert d.summary.text().endswith("sizes differ")
    d._create()
    assert d.project is None
    assert shown["warn"][0][0] == "b.png is 9 x 8 but the project frame size is 8 x 8."


def test_size_outside_range_blocks(app, tmp_path, shown):
    d = StartProjectDialog(folder=str(tmp_path))
    d.set_files([make_png(tmp_path / "a.png", size=(65, 8))])
    d.name.setText("Demo")
    d._create()
    assert d.project is None and "4 to 64" in shown["warn"][0][0]


def test_skipped_files_continue_or_back(app, tmp_path, shown):
    from PIL import Image
    good = make_png(tmp_path / "a.png")
    clear = tmp_path / "b.png"
    Image.new("RGBA", (8, 8), (0, 0, 0, 0)).save(clear)
    d = StartProjectDialog(folder=str(tmp_path))
    d.set_files([good, clear])
    d.name.setText("Demo")
    shown["answer"] = False                                  # Back
    d._create()
    assert d.project is None and "b.png" in shown["choose"][0][1]
    shown["answer"] = True                                   # Continue without these files
    d._create()
    assert d.project and len(d.project.frames) == 1


def test_no_valid_file_left(app, tmp_path, shown):
    from PIL import Image
    clear = tmp_path / "b.png"
    Image.new("RGBA", (8, 8), (0, 0, 0, 0)).save(clear)
    d = StartProjectDialog(folder=str(tmp_path))
    d.set_files([clear])
    d.name.setText("Demo")
    d._create()
    assert d.project is None and "no project was created" in shown["warn"][0][0]


def test_adjustment_warning_still_imports(app, tmp_path, shown):
    d = StartProjectDialog(folder=str(tmp_path))
    d.set_files([make_png(tmp_path / "a.png", colours=((100, 200, 10), (0, 0, 0)))])
    d.name.setText("Demo")
    d._create()
    assert d.project and shown["adjusted"] and "adjusted" in shown["adjusted"][0][0]


def test_open_project_and_damaged(app, tmp_path, shown):
    d = StartProjectDialog(folder=str(tmp_path))
    d.set_files([make_png(tmp_path / "a.png")])
    d.name.setText("Demo")
    d._create()
    out = tmp_path / "Demo.rsr"
    save_project(d.project, out)
    bad = tmp_path / "bad.rsr"
    bad.write_bytes(b"junk")

    d2 = StartProjectDialog(folder=str(tmp_path))
    d2.open_path(bad)
    assert d2.project is None and "could not be opened" in shown["warn"][-1][0]
    d2.open_path(out)
    assert d2.project and d2.project.name == "Demo"
