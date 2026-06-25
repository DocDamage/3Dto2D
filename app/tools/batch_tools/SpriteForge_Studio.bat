@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First-time setup: creating SpriteForge Python environment...
  call setup_windows.bat
)
".venv\Scripts\python.exe" spriteforge_studio.py
if errorlevel 1 pause
