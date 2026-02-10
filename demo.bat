@echo off
REM ============================================================
REM Deepurge AutoClean Agent - Demo File Generator
REM Author: Samuel Campozano Lopez
REM Project: Sui Hackathon 2026
REM ============================================================

echo Generating Demo Files...
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

REM Generate 50 demo files
python demo_generator.py

pause
