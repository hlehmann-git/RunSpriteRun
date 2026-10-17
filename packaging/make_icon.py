"""Makes packaging/RunSpriteRun.ico from the brand picture (run by the Windows build)."""
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src" / "app" / "assets" / "brand.png"


def main() -> None:
    im = Image.open(SRC).convert("RGBA")
    side = max(im.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
    square.save(HERE / "RunSpriteRun.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    main()
