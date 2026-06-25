@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" (
  echo Drag and drop a .blend file onto this BAT file.
  pause
  exit /b 1
)

where blender >nul 2>nul
if errorlevel 1 (
  echo Blender was not found in PATH.
  echo Either add Blender to PATH or edit this BAT and set BLENDER_EXE to your blender.exe path.
  echo Example:
  echo set "BLENDER_EXE=C:\Program Files\Blender Foundation\Blender 4.3\blender.exe"
  pause
  exit /b 1
)

set "BLENDER_EXE=blender"
set "BLEND=%~1"
set "NAME=%~n1"
set "FRAMES=output\%NAME%_ortho_frames"
set "SPRITE=output\%NAME%_ortho_sprite"

"%BLENDER_EXE%" -b --python blender_render_ortho.py -- --blend "%BLEND%" --output "%FRAMES%" --direction front --resolution 512 --fps 12 --start 1 --end 32 --transparent --add-light

if not exist ".venv\Scripts\activate.bat" (
  echo Virtual environment not found. Run setup_windows.bat before packing the sprite sheet.
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat
python spriteforge.py pack --input "%FRAMES%" --output "%SPRITE%" --fps 12 --cell-size 512x512 --anchor bottom-center --solidify 2 --preview-gif --report

echo.
echo Finished. Check:
echo %SPRITE%
pause
