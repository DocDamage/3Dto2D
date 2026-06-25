@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag and drop a SpriteForge output folder onto this BAT file.
  pause
  exit /b 1
)
if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat
python spriteforge_unified.py export-atlas --sprite-dir "%~1" --format texturepacker --copy-image
python spriteforge_unified.py export-atlas --sprite-dir "%~1" --format phaser
python spriteforge_unified.py export-atlas --sprite-dir "%~1" --format pixijs
pause
