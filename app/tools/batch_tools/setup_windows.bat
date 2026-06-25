@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if not errorlevel 1 (
  set "PYLAUNCH=py -3.12"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python was not found. Install Python 3.11 or 3.12, then run this again.
    pause
    exit /b 1
  )
  set "PYLAUNCH=python"
)

echo Creating SpriteForge Python virtual environment...
%PYLAUNCH% -m venv .venv
if errorlevel 1 (
  echo Python 3.12 launcher failed. Trying default Python...
  python -m venv .venv
)
if errorlevel 1 (
  echo Failed to create venv. Make sure Python 3.11 or 3.12 is installed.
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat

echo Installing SpriteForge requirements...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Installing ComfyUI, WAN nodes, Manager, and auto-downloading Wan 2.1 1.3B models...
echo This can download about 10 GB of model files plus temporary cache data.
python spriteforge_unified.py install-all
if errorlevel 1 (
  echo.
  echo Full WAN install failed or was interrupted. You can rerun Install_Everything_With_WAN_Models.bat to resume.
  pause
  exit /b 1
)

echo.
echo Setup complete. WAN model files are installed or verified.
echo Launch SpriteForge_Studio.bat for the unified app.
pause
