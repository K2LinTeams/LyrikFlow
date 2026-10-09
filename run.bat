@echo off
cd /d "%~dp0"
python -u main.py
if errorlevel 1 (
    echo.
    echo LyrikFlow exited with error.
    pause
)
