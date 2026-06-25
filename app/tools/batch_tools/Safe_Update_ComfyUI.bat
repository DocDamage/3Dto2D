@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" call setup_windows.bat
call .venv\Scripts\activate.bat
python spriteforge_unified.py safe-update --custom-nodes
pause
