@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag a folder containing multiple SpriteForge sprite output folders onto this BAT file.
  pause
  exit /b 1
)
python spriteforge_unified.py pack-quality --root "%~1"
python spriteforge_unified.py pack-collect --root "%~1"
python spriteforge_unified.py pack-atlas --root "%~1" --output "%~1\atlas"
pause
