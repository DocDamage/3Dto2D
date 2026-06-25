@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" call setup_windows.bat
call .venv\Scripts\activate.bat
python spriteforge_unified.py download-wan-native --manifest model_manifests\wan21_i2v_480p_14b_native.json
pause
