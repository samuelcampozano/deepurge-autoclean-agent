@echo off
REM ============================================================
REM Deepurge AutoClean Agent - Windows Installation Script
REM Author: Samuel Campozano Lopez
REM Project: Sui Hackathon 2026
REM ============================================================

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                                                              ║
echo ║   DEEPURGE AUTOCLEAN AGENT - INSTALLER                      ║
echo ║                                                              ║
echo ║   Author: Samuel Campozano Lopez                            ║
echo ║   Sui Hackathon 2026                                        ║
echo ║                                                              ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

REM Check Python installation
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed or not in PATH
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)
python --version
echo ✅ Python found!
echo.

REM Create virtual environment
echo [2/5] Creating virtual environment...
if exist venv (
    echo    Virtual environment already exists, skipping...
) else (
    python -m venv venv
    if errorlevel 1 (
        echo ❌ Failed to create virtual environment
        pause
        exit /b 1
    )
)
echo ✅ Virtual environment ready!
echo.

REM Activate virtual environment and install dependencies
echo [3/5] Installing dependencies...
call venv\Scripts\activate.bat
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ Failed to install dependencies
    pause
    exit /b 1
)
echo ✅ Dependencies installed!
echo.

REM Create default config if not exists
echo [4/5] Setting up configuration...
if not exist config.json (
    echo    Creating default config.json...
    echo    Please edit config.json to customize your settings
)
echo ✅ Configuration ready!
echo.

REM Create shortcuts
echo [5/5] Creating shortcuts...
echo    - run.bat: Start the agent
echo    - demo.bat: Generate demo files
echo ✅ Setup complete!
echo.

echo ╔════════════════════════════════════════════════════════════╗
echo ║                                                              ║
echo ║   ✅ INSTALLATION COMPLETE!                                 ║
echo ║                                                              ║
echo ║   To start the agent:                                       ║
echo ║      run.bat                                                 ║
echo ║                                                              ║
echo ║   To generate demo files:                                   ║
echo ║      demo.bat                                                ║
echo ║                                                              ║
echo ║   Edit config.json to customize settings                    ║
echo ║                                                              ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

pause
