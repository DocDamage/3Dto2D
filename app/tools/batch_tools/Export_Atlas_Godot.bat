@echo off
cd /d "%~dp0"
set /p ATLAS=Atlas folder [projects\hero_sprite_pack\atlas\main]: 
if "%ATLAS%"=="" set ATLAS=projects\hero_sprite_pack\atlas\main
python spriteforge_unified.py export-atlas-engine --atlas-dir "%ATLAS%" --engine godot
pause
