@echo off
setlocal
cd /d "%~dp0"
title SpriteForge - Install Python and Git Helper

echo This helper uses winget when available.
echo It installs Python 3.12 and Git, which SpriteForge needs for setup.
echo.
where winget >nul 2>nul
if errorlevel 1 (
  echo winget was not found on this Windows install.
  echo Opening download pages instead.
  start "" "https://www.python.org/downloads/windows/"
  start "" "https://git-scm.com/download/win"
  pause
  exit /b 1
)

echo Installing Python 3.12...
winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements

echo.
echo Installing Git...
winget install -e --id Git.Git --accept-source-agreements --accept-package-agreements

echo.
echo Done. Close this window and run START_HERE.bat again.
pause
