@echo off
echo Starting Student Register Book Application...

rem Find Python in standard locations
set PYTHON_CMD=

rem Try different Python executable possibilities
where python > nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set PYTHON_CMD=python
    goto :found_python
)

where python3 > nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set PYTHON_CMD=python3
    goto :found_python
)

if exist "C:\Python313\python.exe" (
    set PYTHON_CMD=C:\Python313\python.exe
    goto :found_python
)

if exist "C:\Python311\python.exe" (
    set PYTHON_CMD=C:\Python311\python.exe
    goto :found_python
)

if exist "C:\Python310\python.exe" (
    set PYTHON_CMD=C:\Python310\python.exe
    goto :found_python
)

if exist "C:\Python39\python.exe" (
    set PYTHON_CMD=C:\Python39\python.exe
    goto :found_python
)

echo Python not found in PATH or standard locations.
echo Please install Python or specify the path.
pause
exit /b 1

:found_python
echo Using Python: %PYTHON_CMD%

rem Ensure dependencies are installed
echo Installing required packages...
%PYTHON_CMD% -m pip install Flask==3.0.2 sqlalchemy==2.0.27 pandas==2.2.3 openpyxl==3.1.5

rem Run the application
echo Starting application...
%PYTHON_CMD% simple_app.py

pause 