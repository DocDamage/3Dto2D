@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

if not exist "logs" mkdir "logs" >nul 2>nul
set "LOG=logs\launcher_v12_%DATE:~-4%%DATE:~4,2%%DATE:~7,2%.log"
echo ==== SpriteForge v12 bootstrap start %DATE% %TIME% ====>> "%LOG%"

set "PYLAUNCH="

:: Check for py launcher or python in path
py -3.12 --version >nul 2>nul
if not errorlevel 1 ( set "PYLAUNCH=py -3.12" )
if not defined PYLAUNCH (
  py -3.11 --version >nul 2>nul
  if not errorlevel 1 ( set "PYLAUNCH=py -3.11" )
)
if not defined PYLAUNCH (
  py -3 --version >nul 2>nul
  if not errorlevel 1 ( set "PYLAUNCH=py -3" )
)
if not defined PYLAUNCH (
  python --version >nul 2>nul
  if not errorlevel 1 ( set "PYLAUNCH=python" )
)

if not defined PYLAUNCH (
  echo.
  echo Python 3 was not found on your system.
  echo SpriteForge will try to install Python and Git using winget.
  echo.
  call Install_Python_And_Git.bat
  echo.
  echo After Python installs, close this window and run START_HERE.bat again.
  pause
  exit /b 1
)

echo Bootstrap: Using !PYLAUNCH! >> "%LOG%"

:: Call the python-based launcher
!PYLAUNCH! spriteforge_launcher.py %*
exit /b %errorlevel%
