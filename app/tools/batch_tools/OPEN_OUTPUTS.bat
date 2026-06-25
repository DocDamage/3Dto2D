@echo off
cd /d "%~dp0app"
if not exist output mkdir output
start "" "%CD%\output"
