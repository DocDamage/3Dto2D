@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" call setup_windows.bat
call .venv\Scripts\activate.bat
python spriteforge_unified.py generate-sprite --start-comfy --mode t2v --profile rtx3060_12gb --action walk --direction right
pause
