@echo off
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
echo This packages every finished SpriteForge output found under app\output.
echo Use the browser UI Release tab for selecting specific sprite folders.
"%PY%" spriteforge_unified.py release-package --name sprite_release --zip --root output
pause
