@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" (
  echo Drag and drop a SpriteForge output folder onto this BAT file.
  echo The folder should contain sheet.png and sheet.json.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\activate.bat" (
  echo Virtual environment not found. Run setup_windows.bat first.
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat
python spriteforge_unified.py quality-check --sprite-dir "%~1"
pause
