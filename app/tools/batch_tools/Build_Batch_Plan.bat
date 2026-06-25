@echo off
cd /d "%~dp0"
set /p PROJECT=Project JSON path [projects\hero_sprite_pack\project.spriteforge.json]: 
if "%PROJECT%"=="" set PROJECT=projects\hero_sprite_pack\project.spriteforge.json
python spriteforge_unified.py batch-plan --project "%PROJECT%" --pose-guided --frames 33
pause
