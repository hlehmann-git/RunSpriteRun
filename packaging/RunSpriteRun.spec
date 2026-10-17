# PyInstaller recipe: builds dist/RunSpriteRun/ (RunSpriteRun.exe plus its libraries). Run from the project folder:
#   pyinstaller --noconfirm packaging/RunSpriteRun.spec
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ICON = os.path.join(SPECPATH, "RunSpriteRun.ico")

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "src", "app", "assets"), os.path.join("src", "app", "assets"))],
    excludes=["tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="RunSpriteRun",
    console=False,                       # a window app: no black terminal window
    icon=ICON if os.path.exists(ICON) else None,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="RunSpriteRun", upx=False)
