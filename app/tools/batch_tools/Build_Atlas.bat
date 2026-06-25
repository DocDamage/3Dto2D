@echo off
cd /d "%~dp0"
set /p INPUTS=Sprite folder/glob [projects\hero_sprite_pack\sprites\*]: 
if "%INPUTS%"=="" set INPUTS=projects\hero_sprite_pack\sprites\*
set /p OUT=Atlas output [projects\hero_sprite_pack\atlas\main]: 
if "%OUT%"=="" set OUT=projects\hero_sprite_pack\atlas\main
python spriteforge_unified.py atlas --inputs %INPUTS% --output "%OUT%" --cell-size 512x512
pause
