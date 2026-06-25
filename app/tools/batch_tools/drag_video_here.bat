@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" (
  echo Drag and drop a WAN/ComfyUI video file onto this BAT file.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\activate.bat" (
  echo Virtual environment not found. Run setup_windows.bat first.
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat

set "INFILE=%~1"
set "NAME=%~n1"
set "OUTDIR=output\%NAME%_sprite"

python spriteforge.py video --input "%INFILE%" --output "%OUTDIR%" --fps 12 --cell-size 512x512 --key-color auto --key-tolerance 45 --anchor bottom-center --pad 24 --solidify 2 --drop-loop-duplicate --preview-gif --report --save-raw-frames

echo.
echo Finished. Check:
echo %OUTDIR%
pause
