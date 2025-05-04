@echo off
echo Starting Lab Database Web Application (Simple Version)...

:: Find Python
WHERE python >nul 2>nul
IF %ERRORLEVEL% EQU 0 (
    python simple_launch.py
) ELSE (
    echo Python not found. Please install Python and make sure it's in your PATH.
    pause
) 