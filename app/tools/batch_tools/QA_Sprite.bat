@echo off
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag a SpriteForge output folder containing sheet.json onto this BAT, or enter one now.
  set /p SPRITE_DIR=Sprite folder: 
) else (
  set "SPRITE_DIR=%~1"
)
python spriteforge_unified.py qa --sprite-dir "%SPRITE_DIR%"
pause
