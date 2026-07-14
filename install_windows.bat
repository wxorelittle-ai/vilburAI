@echo off
title Brigadir.Pro - Setup

echo ============================================================
echo   Brigadir.Pro - Desktop Setup
echo ============================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python not found. Install Python 3.11 or newer from python.org
    echo During installation, make sure to check "Add python.exe to PATH".
    pause
    exit /b 1
)

echo Creating virtual environment...
python -m venv venv
if not exist venv\Scripts\activate.bat (
    echo.
    echo ERROR: Failed to create the virtual environment. See the message above.
    pause
    exit /b 1
)
call venv\Scripts\activate.bat

python -m pip install --upgrade pip >nul 2>nul

REM Some VPN/proxy tools (V2Ray, Clash, Shadowsocks, etc.) set a SOCKS proxy
REM system-wide. pip needs the "pysocks" package to work through it. Installing
REM it first (best effort - if it fails, that's fine, most setups don't need it).
pip install pysocks >nul 2>nul

echo Installing dependencies, this may take a couple of minutes...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo ============================================================
    echo ERROR: Failed to install dependencies.
    echo ============================================================
    echo This is usually caused by a VPN or proxy app ^(V2Ray, Clash,
    echo Shadowsocks, etc^) routing your connection through a SOCKS proxy.
    echo.
    echo Try this:
    echo   1. Temporarily turn off your VPN/proxy app
    echo   2. Run install_windows.bat again
    echo   3. You can turn the VPN back on after installation finishes -
    echo      the app itself does not need internet access to run.
    echo.
    pause
    exit /b 1
)

pip install -r requirements-desktop.txt
if %errorlevel% neq 0 (
    echo.
    echo WARNING: Could not install the desktop window package ^(pywebview^).
    echo The app will still work - it will just open in your web browser
    echo instead of its own window.
    echo.
)

echo.
echo Setup complete. Starting the application...
echo.

python desktop\launcher.py

pause
