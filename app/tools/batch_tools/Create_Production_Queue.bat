@echo off
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" spriteforge_unified.py queue-create --name hero --actions idle,walk,run,attack_light,hurt --directions right --tier wan21_safe --profile auto
pause
