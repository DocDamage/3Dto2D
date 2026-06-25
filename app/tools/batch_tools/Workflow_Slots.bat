@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" (
  echo Drag and drop an exported ComfyUI API workflow JSON onto this BAT file.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\activate.bat" (
  echo Virtual environment not found. Run setup_windows.bat first.
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat
python spriteforge_unified.py workflow-slots --workflow "%~1"
pause
