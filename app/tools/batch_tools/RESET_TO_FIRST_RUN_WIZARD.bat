@echo off
cd /d "%~dp0app"
del .first_run_complete >nul 2>nul
call START_SPRITEFORGE.bat --wizard
