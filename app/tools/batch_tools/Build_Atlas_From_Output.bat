@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
  echo Virtual environment not found. Run setup_windows.bat first.
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat
python spriteforge_unified.py atlas-build --root output --output output\atlas_build --name spriteforge_atlas
pause
