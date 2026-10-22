# RunSpriteRun

RunSpriteRun is a free Windows desktop program for making and testing sprite animations in the colour limits of classic 8-bit and 16-bit computers and consoles. It works offline, with one project open at a time.

You bring in your sprites (as image files or as one sprite sheet), the program fits them to the colours of the system you chose, and you can then put the frames in order, group them into animations, and **run** them with the keyboard to see how a character will look and move. When you are happy, you export PNG sprite sheets and single frames.

## Systems

Each project is made for one system, and the program keeps the colours inside that system's rules.

| System | Colours in a project | Colour depth |
|---|---|---|
| Sega Genesis / Mega Drive | 16 | 9-bit (RGB 3:3:3), 512 colours |
| Super Nintendo (SNES) | 16 | 15-bit (RGB 5:5:5), 32,768 colours |
| Atari ST | 16 | 9-bit (RGB 3:3:3), 512 colours |
| Atari STE | 32 | 12-bit (RGB 4:4:4), 4,096 colours |
| Amiga | 32 | 12-bit (RGB 4:4:4), 4,096 colours |
| Apple IIgs | 16 | 12-bit (RGB 4:4:4), 4,096 colours |
| Commodore 64 | 16 | fixed palette of 16 colours |
| Apple II (Double Hi-Res) | 16 | fixed palette of 16 colours |

The program counts colours for the whole project, not per tile or per sprite. That is why systems that work with colour limits per tile (for example the NES or the ZX Spectrum) are not included.

## What you can do

- Start a project from image files, from a sprite sheet, or from a blank project, with a frame size from 4 to 128 pixels.
- Have the colours snapped to the chosen system, with a palette and colour editor (the fixed-palette systems have their colours locked). Colours no frame uses stay in the palette until you delete them, and a **+** button adds a new colour with the sliders, the hex box or the pipette.
- Put up to 120 frames on a timeline, select several frames at once, delete, copy and paste them, and rename them.
- Group frames into animations (walk left, walk right, jump and so on), set the resting and start states, and **run** the animation with the keys (W, A, S, D, the diagonals and the number keys).
- **Frame Group Control** (the **Set Rules** button) says which keys play which group, like a game controller: a direction or a combination (W+D, W+D+1) plays a group, once or looping, a rule can fire **only after** another group (for example a left turn only after walking right), and each rule says what happens when the keys are let go. Rules read as one line each, and keys 7, 8, 9 and 0 are action keys that play a group on its own for testing. The window uses the buttons of the system (1 fire button, 3 on the Mega Drive, 6 on the SNES), and Apply saves your changes in one go.
- Edit pixels in Edit mode: pencil, eraser, bucket, line, square, circle, select, move, mirror drawing and three layers, with undo and redo.
- **Edit > Shrink Sprite** makes every frame smaller (87.5%, 75%, 50%, 25% or 12.5% of the size) and snaps the result to the colours already in the project.
- **Edit > Reduce Palette** lowers the number of colours in a project. The program picks the colours that matter most to the picture and moves every other pixel to the nearest one. A From / To preview shows the result before anything changes.
- Create a blank sprite sheet for any system, ready to paint on in another program.
- Export PNG sprite sheets (all frames and one per animation group) and one PNG per frame. Every Save and Export also writes `<Project>_Rules.txt` (tab-separated tables) and `<Project>_Rules.json` (for game developers) describing the groups and the key rules.

Shrink Sprite and Reduce Palette cannot be undone. Both warn you first, and nothing is written to disk until you save.

## Report a problem

Found a bug or have an idea? Please [open an issue](https://github.com/hlehmann-git/runspriterun/issues/new/choose) and fill in the short form. A project file or a screenshot helps a lot.

## Help

The full user guide is in [docs/HELP.md](docs/HELP.md).

## Getting the program

### Windows installer (easiest)

The program needs Windows 10 or 11 (64-bit). The installer includes everything it needs, so you do not need Python.

1. Download the latest `RunSpriteRun_Setup_<version>.exe` from the [Releases page](https://github.com/hlehmann-git/RunSpriteRun/releases/latest) (under **Assets**).
2. Double-click it. Windows may show "Windows protected your PC", because the installer is not signed. Click **More info**, then **Run anyway**.
3. Choose where to install it, then click **Install**.

Your projects, exports and blank sprite sheets are saved in folders inside the install folder, and the Start Menu shortcut "RunSpriteRun files" opens it. Uninstalling (Windows Settings, Installed apps) removes the program and leaves your projects.

### Run it from the source code

You need Windows and Python 3.12 (64-bit, from python.org, with "Add python.exe to PATH" ticked).

```
git clone https://github.com/hlehmann-git/RunSpriteRun.git
cd RunSpriteRun
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

If the activate step is blocked, use a Command Prompt (cmd) instead of PowerShell. To run the tests, install `requirements-dev.txt` as well and run `python -m pytest`. The full suite takes about 15 to 20 minutes, and it can also be run one test file at a time.

To build the Windows installer yourself, see [docs/BUILDING.md](docs/BUILDING.md).

## Examples

The `Examples` folder holds ready-made projects for every system, in `Examples/Projects/<System>/<Project>/<Project>.rsr`. Open one with File > Open to see how the same sprite looks with each system's palette. See `Examples/README.txt` for the layout.

The example sprites are taken from Metal Gear Solid 3 and from Gods (the Bitmap Brothers game). They are included as examples only. The characters and games belong to their owners, and RunSpriteRun is not affiliated with or endorsed by them.

## Files and folders

Projects are stored one folder per project (`Projects\<Name>\<Name>.rsr` and the exported images beside it). A project file (`.rsr`) is a zip holding the project data and one PNG per frame. Settings are kept in a small file in your Windows application data folder, never inside a project.

## Licence

RunSpriteRun is released under the [MIT licence](LICENSE).

Made by Harley Lehmann.
