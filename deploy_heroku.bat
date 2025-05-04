@echo off
echo Student Register Book - Heroku Deployment
echo =======================================================
echo.

:: Check if Heroku CLI is installed
where heroku >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Heroku CLI is not installed on your system.
    echo Please install Heroku CLI first: https://devcenter.heroku.com/articles/heroku-cli
    echo.
    pause
    exit /b 1
)

:: Check if Git is installed
where git >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Git is not installed on your system.
    echo Please install Git first: https://git-scm.com/downloads
    echo.
    pause
    exit /b 1
)

echo Setting up files for Heroku deployment...

:: Copy app_heroku.py to app.py for deployment
echo Preparing app.py for Heroku...
copy app_heroku.py app.py /Y

:: Install required packages
echo Installing required packages...
pip install -r requirements-heroku.txt

:: Log in to Heroku if needed
echo.
echo Please log in to Heroku (a browser window might open)
heroku login

:: Create Heroku app or use existing one
echo.
set /p APP_NAME="Enter your Heroku app name (leave blank for random name): "

if "%APP_NAME%"=="" (
    echo Creating Heroku app with random name...
    heroku create
) else (
    echo Creating Heroku app %APP_NAME%...
    heroku create %APP_NAME%
)

:: Add PostgreSQL addon
echo Adding PostgreSQL database...
heroku addons:create heroku-postgresql:hobby-dev

:: Set environment variables
echo Setting environment variables...
heroku config:set FLASK_ENV=production
heroku config:set SECRET_KEY=%RANDOM%%RANDOM%%RANDOM%

:: Configure git
echo.
echo Configuring git...
git init
git add .
git commit -m "Initial Heroku deployment"

:: Setup Git remote for Heroku
echo.
echo Setting up git remote for Heroku...
heroku git:remote -a %APP_NAME%

:: Deploy to Heroku
echo.
echo Deploying to Heroku...
git push heroku main

:: Open the app in browser
echo.
echo Opening your application in the browser...
heroku open

echo.
echo =======================================================
echo Your app should now be deployed to Heroku!
echo Visit your app at: https://%APP_NAME%.herokuapp.com
echo =======================================================
echo.
pause 