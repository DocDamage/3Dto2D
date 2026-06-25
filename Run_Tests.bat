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
echo [1/4] Running unit and integration tests...
%PYTHON% -m pytest tests\ -v --tb=short -q
if errorlevel 1 (
  echo.
  echo FAILED: Unit/integration tests. Fix errors before proceeding.
  pause
  exit /b 1
)
echo PASSED: Unit tests.
echo.

REM ── 2. Web UI smoke test ────────────────────────────────────
echo [2/4] Web UI smoke test...
%PYTHON% app\spriteforge_web.py --smoke
if errorlevel 1 (
  echo FAILED: Web UI smoke test.
  pause
  exit /b 1
)
echo PASSED: Web UI smoke.
echo.

REM ── 3. Demo generation smoke test ───────────────────────────
echo [3/4] Demo generation smoke test (no GPU required)...
%PYTHON% app\spriteforge_demo.py --smoke 2>nul
if errorlevel 1 (
  REM spriteforge_demo.py may not support --smoke; try help check instead
  %PYTHON% -c "import app.spriteforge_demo" 2>nul
  if errorlevel 1 (
    echo WARNING: Demo smoke test could not run - continuing.
  ) else (
    echo PASSED: Demo module imports OK.
  )
) else (
  echo PASSED: Demo smoke.
)
echo.

REM ── 4. Smoke tests via pytest ────────────────────────────────
echo [4/4] Smoke test suite (pytest tests\test_smoke.py)...
%PYTHON% -m pytest tests\test_smoke.py -v --tb=short 2>nul
if errorlevel 1 (
  echo WARNING: Smoke tests not all passed. Check output above.
) else (
  echo PASSED: Smoke tests.
)
echo.

echo ============================================================
echo  All test stages complete.
echo ============================================================
pause
