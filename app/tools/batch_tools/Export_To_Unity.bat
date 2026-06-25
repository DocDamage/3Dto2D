@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag a SpriteForge output folder containing sheet.png and sheet.json onto this BAT.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\activate.bat" call setup_windows.bat
call .venv\Scripts\activate.bat
python spriteforge_unified.py export-engine --engine unity --sprite-dir "%~1"
pause
