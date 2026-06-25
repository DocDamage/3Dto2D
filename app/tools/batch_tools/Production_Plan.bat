@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
  echo Virtual environment not found. Run setup_windows.bat first.
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat
python spriteforge_unified.py production-plan --character "single full body original game hero, clean silhouette" --style "clean 2D game sprite, crisp outline" --direction right --pose --seeds 2 --output output\production_plan
pause
