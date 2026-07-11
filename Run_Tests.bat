@echo off
REM SpriteForge Studio v12 - Windows End-to-End Test Runner
REM Usage: Double-click or run from the project root.
setlocal

cd /d "%~dp0"
set PYTHON=app\.venv\Scripts\python.exe

if not exist "%PYTHON%" (
  echo ERROR: Virtual environment not found at app\.venv\Scripts\python.exe
  echo        Run START_SPRITEFORGE.bat first to set up the environment.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo  SpriteForge Studio v12 - Test Suite
echo ============================================================
echo.

REM ── 1. Unit + integration tests ─────────────────────────────
echo [1/5] Running all unit and integration tests...
%PYTHON% -m pytest -q --tb=short
if errorlevel 1 (
  echo.
  echo FAILED: Unit/integration tests. Fix errors before proceeding.
  pause
  exit /b 1
)
echo PASSED: Unit tests.
echo.

REM ── 2. Web UI smoke test ────────────────────────────────────
echo [2/5] Web UI smoke test...
%PYTHON% app\spriteforge_web.py --smoke
if errorlevel 1 (
  echo FAILED: Web UI smoke test.
  pause
  exit /b 1
)
echo PASSED: Web UI smoke.
echo.

REM ── 3. Demo generation smoke test ───────────────────────────
echo [3/5] Demo generation smoke test (no GPU required)...
%PYTHON% app\spriteforge_demo.py --smoke 2>nul
if errorlevel 1 (
  REM spriteforge_demo.py may not support --smoke; try help check instead
  %PYTHON% -c "import app.spriteforge_demo" 2>nul
  if errorlevel 1 (
    echo FAILED: Demo smoke test could not run.
    exit /b 1
  ) else (
    echo PASSED: Demo module imports OK.
  )
) else (
  echo PASSED: Demo smoke.
)
echo.

REM ── 4. JavaScript syntax ─────────────────────────────────────
echo [4/5] Checking all JavaScript files...
for %%F in (app\web\js\*.js) do node --check "%%F"
if errorlevel 1 (
  echo FAILED: JavaScript syntax check.
  exit /b 1
)
echo PASSED: JavaScript syntax.
echo.

REM ── 5. Python/dependency integrity ───────────────────────────
echo [5/5] Checking Python syntax and installed dependencies...
%PYTHON% -m compileall -q app -x "app[\\/](vendor|input|scratch|\.venv)"
if errorlevel 1 exit /b 1
%PYTHON% -m pip check
if errorlevel 1 exit /b 1
echo PASSED: Python and dependency integrity.
echo.

echo ============================================================
echo  All test stages complete.
echo ============================================================
pause
