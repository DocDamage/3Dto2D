@echo off
setlocal
cd /d "%~dp0"

set "PY=python"
if exist "app\.venv\Scripts\python.exe" set "PY=app\.venv\Scripts\python.exe"

echo SpriteForge LPC release confidence check
echo.

"%PY%" -m pytest tests/test_lpc_parts_service.py tests/test_web_api.py tests/test_training_dataset_service.py -q
if errorlevel 1 exit /b 1

node --check app\web\js\app_forms.js
if errorlevel 1 exit /b 1

echo.
echo LPC release confidence check passed.
