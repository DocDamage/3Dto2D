@echo off
cd /d "%~dp0"
set /p NAME=Project name [hero_sprite_pack]: 
if "%NAME%"=="" set NAME=hero_sprite_pack
set /p CHAR=Character description [single full body original game character]: 
if "%CHAR%"=="" set CHAR=single full body original game character
python spriteforge_unified.py project-init --name "%NAME%" --character "%CHAR%" --actions idle,walk,run,attack_light,jump,hurt --views right,left
pause
