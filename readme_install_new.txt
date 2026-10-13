Part A: Install Python (once per PC)

1. Go to python.org, then Downloads, then Windows, and download the Windows installer (64-bit) for Python 3.12. Use Python 3.12.10 (the last 3.12 release with a Windows installer), or the newest 3.12 installer listed. "64-bit" is the same as "AMD64" and works on Intel processors too. Avoid "embeddable", "ARM64", "32-bit", Microsoft Store versions and release candidates.
2. Run the installer.
3. On the first screen, tick Add python.exe to PATH at the bottom. You can then choose either Install Now or Customize installation, SO LONG AS Add python.exe to PATH IS TICKED.
4. Click Install Now (or finish the Customize installation screens) and wait for it to finish, then click Close.

What has happened: Python 3.12 is now installed on your PC and Windows knows where to find it, so you can type python in any terminal window. You only do Part A once per PC.

Part B: Unzip the app

1. Right-click RunSpriteRun_v2.0.1.zip and choose Extract All.
2. Pick a folder you'll remember, for example C:\Dev\. You should end up with C:\Dev\RunSpriteRun\, with main.py directly inside it.

What has happened: The RunSpriteRun folder is now on your PC, with the program, the Examples projects and the empty Projects, Exports and Blank sprite sheets folders inside it. Nothing is installed yet.

Part C: Set up the app (once per install)

1. Open the RunSpriteRun folder in File Explorer.
2. Click the address bar, type cmd and press Enter. A terminal opens already in that folder.
3. Check Python is found by typing python --version. It should say 3.12.something.
4. Create the virtual environment: python -m venv .venv
5. Switch it on: .venv\Scripts\activate. You'll see (.venv) at the start of the line.
6. Install the libraries: pip install -r requirements.txt. This downloads PySide6 and Pillow and takes a minute or two.

What has happened: RunSpriteRun now has its own private set of libraries (PySide6 and Pillow) in a .venv folder inside the RunSpriteRun folder. This does not affect any other Python project on your PC. You only do Part C once per install.

Part D: Run it (every time)

1. Open a terminal in the RunSpriteRun folder, as in step C2.
2. Type .venv\Scripts\activate.
3. Type python main.py.

What has happened: The RunSpriteRun window opens and you can start working. To run it again later, repeat Part D only.

If step 3 of Part C says "python is not recognized", the PATH box wasn't ticked. Run the installer again, choose Modify, and tick the PATH option. If you use PowerShell instead of cmd and the activate step is blocked, use cmd, which avoids that problem.
