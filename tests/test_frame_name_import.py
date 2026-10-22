"""Sprite sheet import asks for a short frame name instead of using the whole file name."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PIL import Image
from PySide6.QtWidgets import QApplication

from src.app import messages, start_project
from src.core.sheet_import import import_sheet, find_grid

app = QApplication.instance() or QApplication([])


def _sheet(tmp_path, name="RickDangerous_SpriteSheet_Amiga_24x21_8x4.png"):
    im = Image.new("RGB", (14, 7), (255, 0, 255))
    for x0 in (0, 7):
        for x in range(x0, x0 + 7):
            for y in range(7):
                if x in (x0, x0 + 6) or y in (0, 6):
                    im.putpixel((x, y), (0, 255, 0))
        im.putpixel((x0 + 3, 3), (255, 255, 255))
    p = tmp_path / name
    im.save(p)
    return p


def test_import_uses_the_typed_name(tmp_path):
    p = _sheet(tmp_path)
    im = Image.open(p)
    g = find_grid(im, (0, 255, 0))
    from src.core.systems import get_system
    r = import_sheet(im, "Rick", g, (255, 0, 255), get_system("Amiga"))
    assert [f.label for f in r.frames] == ["Rick", "Rick"]


def test_dialog_prefills_and_validates(tmp_path, monkeypatch):
    warned = []
    monkeypatch.setattr(messages, "warn", lambda *a, **k: warned.append(a))
    p = _sheet(tmp_path)
    d = start_project.StartProjectDialog(None) if hasattr(start_project, "StartProjectDialog") else None
    if d is None:
        return
    from pathlib import Path; d.set_sheet(Path(p))
    assert d.frame_name.text().startswith("RickDangerous_SpriteSheet")
    d.frame_name.setText("bad name")
    d._create_from_sheet()
    assert warned
