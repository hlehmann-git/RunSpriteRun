from pathlib import Path
from PIL import Image


def make_png(path: Path, size=(8, 8), colours=((0, 0, 0),), mode="RGB") -> Path:
    """Write a PNG whose pixels cycle through `colours`."""
    im = Image.new(mode, size)
    px = [colours[i % len(colours)] for i in range(size[0] * size[1])]
    im.putdata(px)
    im.save(path)
    return path
