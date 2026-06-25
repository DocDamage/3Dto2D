@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag and drop a SpriteForge output folder onto this BAT file.
  pause
  exit /b 1
)
if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat
python spriteforge_unified.py autofix-sprite --input "%~1" --drop-loop-duplicate --stabilize-anchor --deflicker --solidify 2
pause
