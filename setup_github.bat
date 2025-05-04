@echo off
echo Setting up GitHub repository for Student Register Book...
echo -------------------------------------------------------

:: Check if Git is installed
where git >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Git is not installed or not in your PATH.
    echo Please install Git from https://git-scm.com/downloads and try again.
    pause
    exit /b 1
)

:: Initialize the repository
echo Initializing Git repository...
git init

:: Add all files (excluding those in .gitignore)
echo Adding files to repository...
git add .

:: Prompt for GitHub username
set /p GITHUB_USERNAME="Enter your GitHub username: "

:: Replace USERNAME placeholders in files
echo Updating GitHub username in files...
powershell -Command "(Get-Content README.md) -replace 'USERNAME', '%GITHUB_USERNAME%' | Set-Content README.md"
powershell -Command "(Get-Content docs/index.html) -replace 'USERNAME', '%GITHUB_USERNAME%' | Set-Content docs/index.html"
powershell -Command "(Get-Content docs/_config.yml) -replace 'USERNAME', '%GITHUB_USERNAME%' | Set-Content docs/_config.yml"

:: Commit the changes
echo Creating initial commit...
git add .
git commit -m "Initial commit"

:: Set up the GitHub repository
echo.
echo Please create a new repository on GitHub:
echo 1. Go to https://github.com/new
echo 2. Repository name: Lab_Database
echo 3. Leave "Initialize this repository with a README" unchecked
echo 4. Click "Create repository"
echo.
pause

:: Push to GitHub
echo Pushing to GitHub...
set /p CONTINUE="Did you create the repository on GitHub? (Y/N): "
if /i "%CONTINUE%" NEQ "Y" (
    echo Setup paused. Please create the repository and run this script again.
    pause
    exit /b 1
)

git remote add origin https://github.com/%GITHUB_USERNAME%/Lab_Database.git
git branch -M main
git push -u origin main

:: Set up GitHub Pages
echo.
echo Setting up GitHub Pages:
echo 1. Go to https://github.com/%GITHUB_USERNAME%/Lab_Database/settings/pages
echo 2. Under "Source", select "Deploy from a branch"
echo 3. Under "Branch", select "main" and "/docs" folder
echo 4. Click "Save"
echo.
echo Your GitHub Pages site will be available at: https://%GITHUB_USERNAME%.github.io/Lab_Database/
echo.
pause 