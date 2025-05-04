@echo off
:: Batch file to manage and activate a Python virtual environment in the terminal

:: Define the virtual environment directory name
set VENV_DIR=venv

:: Check if the virtual environment exists
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo Virtual environment not found. Creating one...
    python -m venv %VENV_DIR%
    if %ERRORLEVEL% neq 0 (
        echo Failed to create the virtual environment. Please check your Python installation.
        pause
        exit /b 1
    )
    echo Virtual environment created successfully.
)

:: Check PowerShell execution policy
for /f "tokens=*" %%i in ('powershell Get-ExecutionPolicy') do set EXEC_POLICY=%%i
if /i "%EXEC_POLICY%"=="Restricted" (
    echo PowerShell execution policy is Restricted. Temporarily bypassing it...
    powershell Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
)

# .\myenv\Scripts\Activate.ps1

:: Activate the virtual environment in the terminal
echo Activating the virtual environment in the terminal...
cmd /k "%VENV_DIR%\Scripts\activate.bat"
