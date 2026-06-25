@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat
echo Example remote run. Edit this BAT with your remote server/workflow/prompt.
python spriteforge_unified.py remote-generate --server http://YOUR_REMOTE_HOST:8188 --workflow workflows\your_remote_api_workflow.json --prompt "single full body character idle cycle, locked camera, green background" --convert
pause
