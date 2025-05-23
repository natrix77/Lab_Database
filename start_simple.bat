@echo off
echo Starting Student Management System...
echo.

REM Kill any existing Python processes that might be using the same port
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM pythonw.exe >nul 2>&1
timeout /t 2 >nul

REM Start the simple app with explicit host and port settings
start "Student Management System" pythonw simple_app.pyw

echo.
echo Application should now be running at:
echo http://127.0.0.1:5050/ 
echo or
echo http://localhost:5050/
echo.
echo Default login credentials:
echo   Username: admin
echo   Password: admin123
echo.
echo Press any key to exit...
pause >nul 