@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" (
  echo Drag and drop a folder of PNG frames onto this BAT file.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\activate.bat" (
  echo Virtual environment not found. Run setup_windows.bat first.
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat

set "INFOLDER=%~1"
set "NAME=%~n1"
set "OUTDIR=output\%NAME%_sprite"

python spriteforge.py pack --input "%INFOLDER%" --output "%OUTDIR%" --fps 12 --cell-size 512x512 --anchor bottom-center --solidify 2 --drop-loop-duplicate --preview-gif --report

echo.
echo Finished. Check:
echo %OUTDIR%
pause
