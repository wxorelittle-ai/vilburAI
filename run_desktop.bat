@echo off
title Brigadir.Pro

if not exist venv\Scripts\activate.bat (
    echo It looks like the app is not installed yet.
    echo Please run install_windows.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
python desktop\launcher.py
pause
