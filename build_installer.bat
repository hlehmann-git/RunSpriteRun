@echo off
rem Builds the RunSpriteRun Windows installer on this PC.
rem Needs: the .venv folder set up (see BUILD_INSTALLER.txt) and Inno Setup 6 installed.
setlocal
cd /d "%~dp0"
title Build the RunSpriteRun installer

set "PY=.venv\Scripts\python.exe"

echo.
echo ===== RunSpriteRun installer build =====
echo.

if not exist "%PY%" (
  echo The .venv folder was not found in this folder.
  echo Set it up first: see Part 4 in BUILD_INSTALLER.txt.
  goto :fail
)

echo [1/6] Reading the version number...
"%PY%" -c "from src.version import VERSION; print(VERSION)" > build_version.txt
if errorlevel 1 goto :fail
set /p VERSION=<build_version.txt
del build_version.txt
if "%VERSION%"=="" goto :fail
echo       Version %VERSION%

echo [2/6] Checking PyInstaller is installed...
"%PY%" -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
  echo       Not found. Installing it now...
  "%PY%" -m pip install pyinstaller
  if errorlevel 1 goto :fail
)

echo [3/6] Making the program icon...
"%PY%" packaging\make_icon.py
if errorlevel 1 goto :fail

echo [4/6] Packaging the program. This takes a few minutes...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
"%PY%" -m PyInstaller --noconfirm --distpath dist --workpath build packaging\RunSpriteRun.spec
if errorlevel 1 goto :fail
if not exist "dist\RunSpriteRun\RunSpriteRun.exe" goto :fail

echo [5/6] Finding Inno Setup...
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
  echo       Inno Setup 6 was not found. Install it from jrsoftware.org, then run this again.
  goto :fail
)
echo       Found %ISCC%

echo [6/6] Building the installer...
if exist dist_installer rmdir /s /q dist_installer
"%ISCC%" "/DAppVersion=%VERSION%" packaging\RunSpriteRun.iss
if errorlevel 1 goto :fail

echo.
echo ===== Done =====
echo Your installer is in the dist_installer folder:
echo   RunSpriteRun_Setup_v%VERSION%.exe
echo.
start "" explorer "%~dp0dist_installer"
pause
exit /b 0

:fail
echo.
echo ===== The build stopped because of a problem =====
echo Take a screenshot of this window, including the lines above, and send it to Claude.
echo.
pause
exit /b 1
