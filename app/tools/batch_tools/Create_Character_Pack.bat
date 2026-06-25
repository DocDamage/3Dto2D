@echo off
setlocal
cd /d "%~dp0"
python spriteforge_unified.py pack-init --name my_character_pack --character "single full body original game character, consistent outfit, clean silhouette" --actions idle,walk,run,attack_light,hurt,death --directions front,right,back,left --pose-guided --posepacks
pause
