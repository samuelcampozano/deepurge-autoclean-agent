@echo off
title Deepurge Dashboard - Walrus Blob Viewer
echo.
echo  ========================================
echo    Deepurge Dashboard
echo    Walrus Blob Viewer
echo  ========================================
echo.

:: Check for Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found! Please install Python 3.10+
    pause
    exit /b 1
)

:: Install dashboard dependencies if needed
echo [*] Checking dashboard dependencies...
pip install flask flask-cors requests >nul 2>&1

:: Run dashboard
echo [*] Starting dashboard on http://localhost:5050
echo [*] Press Ctrl+C to stop
echo.
cd /d "%~dp0dashboard"
python app.py
