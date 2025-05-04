@echo off
echo Starting Lab Database application...

:: Try to find Python in common locations
set PYTHON_FOUND=0

:: Try Python 3 from standard locations
IF EXIST "C:\Python311\python.exe" (
    set PYTHON_PATH=C:\Python311\python.exe
    set PYTHON_FOUND=1
) ELSE IF EXIST "C:\Python310\python.exe" (
    set PYTHON_PATH=C:\Python310\python.exe
    set PYTHON_FOUND=1
) ELSE IF EXIST "C:\Python39\python.exe" (
    set PYTHON_PATH=C:\Python39\python.exe
    set PYTHON_FOUND=1
) ELSE IF EXIST "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set PYTHON_PATH=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
    set PYTHON_FOUND=1
) ELSE IF EXIST "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set PYTHON_PATH=%LOCALAPPDATA%\Programs\Python\Python310\python.exe
    set PYTHON_FOUND=1
) ELSE IF EXIST "%LOCALAPPDATA%\Programs\Python\Python39\python.exe" (
    set PYTHON_PATH=%LOCALAPPDATA%\Programs\Python\Python39\python.exe
    set PYTHON_FOUND=1
)

IF %PYTHON_FOUND%==0 (
    echo Python not found. Please install Python 3.9 or newer.
    pause
    exit /b 1
)

echo Using Python: %PYTHON_PATH%

:: Set Flask environment variables
set FLASK_APP=run.py
set FLASK_ENV=development
set FLASK_DEBUG=1

:: Install required packages if needed
%PYTHON_PATH% -m pip install flask flask-wtf sqlalchemy

:: Run the application
echo Starting server...
%PYTHON_PATH% run.py

pause 