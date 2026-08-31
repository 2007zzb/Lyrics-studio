@echo off
title Lyric Studio - Launcher (ASCII)
cd /d "%~dp0"
setlocal

echo ============================================================
echo   Lyric Studio  /  XiaoBo Lyric Workshop
echo   This is the ASCII fallback launcher. No Chinese characters.
echo ============================================================
echo.

set "PYCMD="
where python >nul 2>&1
if not errorlevel 1 set "PYCMD=python"
if not defined PYCMD (
    where py >nul 2>&1
    if not errorlevel 1 set "PYCMD=py -3"
)
if not defined PYCMD (
    echo [ERROR] Python not found.
    echo Please install Python from https://www.python.org/downloads/
    echo Remember to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

echo [1/3] Python found:
%PYCMD% --version
echo.

if exist ".venv\Scripts\python.exe" (
    echo [2/3] venv already exists, skip.
) else (
    echo [2/3] Creating virtual environment, please wait...
    %PYCMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
)
call .venv\Scripts\activate.bat
echo.

echo [3/3] Installing dependencies, 1-3 minutes on first run...
python -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo.

echo ============================================================
echo   Launching... The app window will appear shortly.
echo ============================================================
echo.
python main.py

if errorlevel 1 (
    echo.
    echo [ERROR] App crashed. Please take a screenshot.
    echo.
)

endlocal
pause
