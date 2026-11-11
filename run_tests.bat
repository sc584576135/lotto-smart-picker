@echo off
REM ============================================================
REM  DLT Lotto Predictor - one-click unit tests
REM  Usage: double-click or run  run_tests.bat
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM ---------- 1. locate Python (prefer the Win7-compatible 3.8 env) ----------
set "PY="
REM Priority 1: bundled py38 used for building the exe
if exist "D:\PYWD\py38\python.exe" set "PY=D:\PYWD\py38\python.exe"
REM Priority 2: py launcher
if not defined PY (
    where py >nul 2>nul && for /f "delims=" %%i in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i"
)
REM Priority 3: PATH python
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    if exist "C:\Python315\python.exe" set "PY=C:\Python315\python.exe"
)
if not defined PY (
    echo [x] Python not found. Edit PY path in this file or install Python.
    pause
    exit /b 1
)

REM sanity check: required libs must import, otherwise tests are meaningless
"%PY%" -c "import tkinter,requests,pandas,numpy,matplotlib,sklearn" >nul 2>nul
if errorlevel 1 (
    echo [x] Python found at "%PY%" but required libraries are missing.
    echo     Try: D:\PYWD\py38\python.exe  ^(Python 3.8, Win7-compatible^)
    pause
    exit /b 1
)

echo [*] Using Python: %PY%
echo.

REM ---------- 2. run all test suites ----------
set "FAIL=0"
for %%T in (test_lotto_core test_trend test_lotto_ai test_coverage test_servers test_datasource test_gui_datasource) do (
    echo ===== Running %%T =====
    "%PY%" "%~dp0%%T.py"
    if errorlevel 1 (
        echo [FAILED] %%T
        set "FAIL=1"
    ) else (
        echo [PASS]  %%T
    )
    echo.
)

REM ---------- 3. summary ----------
echo ============================================================
if "%FAIL%"=="1" (
    echo [RESULT] Some tests FAILED. Check logs above.
    pause
    exit /b 1
) else (
    echo [RESULT] ALL TESTS PASSED.
    pause
    exit /b 0
)