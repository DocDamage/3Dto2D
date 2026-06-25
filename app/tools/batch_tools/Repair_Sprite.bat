@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag a SpriteForge output folder containing sheet.json onto this BAT file.
  pause
  exit /b 1
)
python spriteforge_unified.py repair-sprite --sprite-dir "%~1" --anchor bottom-center --pad 8 --drop-loop-duplicate
pause
