# Building the Windows installer

This turns the project into a single installer file, `RunSpriteRun_Setup_<version>.exe`, that installs on any 64-bit Windows 10 or 11 PC. The PC that runs the installer does not need Python.

You do steps 1 to 4 once. Step 5 is the build itself and is repeated for each new version.

## 1. Choose a build folder outside OneDrive

Use a short local path such as `C:\Dev`. A build creates thousands of small files, and a sync tool such as OneDrive can slow or break it.

## 2. Install Inno Setup 6 (once)

Download **Inno Setup 6** (not version 7) from jrsoftware.org and run it with the default options. Check that `C:\Program Files (x86)\Inno Setup 6\ISCC.exe` exists. The build script finds it by itself.

## 3. Get the code

Clone the repository, or download and unzip a release, so that `main.py` and `build_installer.bat` are directly inside the project folder (for example `C:\Dev\RunSpriteRun`).

## 4. Set up Python for the project (once)

Install Python 3.12 (64-bit) with "Add python.exe to PATH" ticked, then, in a Command Prompt opened in the project folder:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install --require-hashes -r packaging\build-tools.txt
```

This puts PySide6, Pillow and PyInstaller in a private `.venv` folder that does not affect anything else on the PC. The build tools are exact versions listed in `packaging/build-tools.txt`, each checked against its published hash; `build_installer.bat` checks them again every time it runs.

## 5. Build (every time)

Double-click `build_installer.bat`. It shows six steps and takes about five minutes; the packaging step (4 of 6) is the slow one and prints a lot of text. When it says Done, the `dist_installer` folder opens and holds `RunSpriteRun_Setup_<version>.exe`. The `build` and `dist` folders it creates can be deleted at any time.

The script reads the version from `src/version.py`, runs PyInstaller (with `packaging/RunSpriteRun.spec`) to make the program folder, and then Inno Setup (with `packaging/RunSpriteRun.iss`) to make the installer.

## 6. Try the installer

Run the new `.exe`, or copy it to a USB stick and run it on another PC. Windows may show "Windows protected your PC" because the installer is not signed: click **More info**, then **Run anyway**.

## New version

Raise the number in `src/version.py`, and repeat step 5.

## If something goes wrong

- "The .venv folder was not found": step 4 was not done in this folder.
- "Inno Setup 6 was not found": check step 2, and that `ISCC.exe` is at the path above.
- Antivirus removes files while building: pause it for the build, or exclude the project folder.
