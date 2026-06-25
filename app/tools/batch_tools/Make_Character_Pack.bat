@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat
set /p NAME=Character name: 
set /p DESC=Character description: 
python spriteforge_unified.py character-pack --name "%NAME%" --description "%DESC%" --actions idle,walk,run,attack_light,attack_heavy,hurt,death --directions right,left
pause
