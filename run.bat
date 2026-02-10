@echo off
REM ============================================================
REM Deepurge AutoClean Agent - Run Script
REM Author: Samuel Campozano Lopez
REM Project: Sui Hackathon 2026
REM ============================================================

echo Starting Deepurge AutoClean Agent...
echo.

REM Activate virtual environment
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo ⚠️ Virtual environment not found!
    echo Please run install.bat first
    pause
    exit /b 1
)

REM Run the agent
python agent.py

REM Keep window open if there's an error
if errorlevel 1 (
    echo.
    echo Agent exited with an error
    pause
)
