@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
  echo Virtual environment not found. Run setup_windows.bat first.
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat

echo Edit this BAT file if your ComfyUI output path is different.
set "COMFY_OUT=C:\ComfyUI\output"

python spriteforge.py watch --folder "%COMFY_OUT%" --output output --pattern *.mp4 --fps 12 --cell-size 512x512 --key-color auto --anchor bottom-center --solidify 2 --drop-loop-duplicate --preview-gif --report
pause
