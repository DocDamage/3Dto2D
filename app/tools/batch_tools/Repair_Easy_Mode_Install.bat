@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title SpriteForge Studio v12 - Repair Easy Mode

echo This will rebuild the local SpriteForge Python environment.
echo It will NOT delete ComfyUI, models, outputs, or projects.
echo.
choice /C YN /M "Continue"
if errorlevel 2 exit /b 0

set "PYVER="
py -3.12 --version >nul 2>nul
if not errorlevel 1 set "PYVER=3.12"
if not defined PYVER (
  py -3.11 --version >nul 2>nul
  if not errorlevel 1 set "PYVER=3.11"
)
if not defined PYVER (
  py -3 --version >nul 2>nul
  if not errorlevel 1 set "PYVER=3"
)
if not defined PYVER (
  echo Python was not found. Install Python 3.11 or 3.12 and run this again.
  pause
  exit /b 1
)

echo !PYVER!> .python_version
if exist ".venv" rmdir /s /q ".venv"
py -!PYVER! -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt

echo.
echo Repair complete. Launching Easy Mode...
".venv\Scripts\python.exe" spriteforge_easy.py
pause
