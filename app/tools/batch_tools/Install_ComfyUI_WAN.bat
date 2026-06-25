@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo SpriteForge environment is missing. Run START_HERE.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" spriteforge_unified.py install-all
pause
