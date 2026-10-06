@echo off
REM ========================================================
REM Adaptive Study Tutor - Git Push Helper for Windows
REM ========================================================
echo ========================================================
echo        Pushing Adaptive Study Tutor to GitHub
echo ========================================================

REM Check if git is initialized
if not exist ".git" (
    echo Initializing git repository...
    git init
    git branch -M main
)

REM Verify .env and database are ignored
echo Checking status...
git status --porcelain .env >nul 2>&1
if %errorlevel% equ 0 (
    echo [SECURITY WARNING] .env was tracked! Removing it from cache...
    git rm --cached .env
)

echo Adding files to git...
git add .

echo Creating commit...
git commit -m "feat: complete runnable Adaptive Study Tutor implementation for Task 4"

REM Check if remote exists
git remote get-url origin >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo No git remote 'origin' found.
    set /p REPO_URL="Enter your GitHub repository URL (e.g. https://github.com/your-username/adaptive-study-tutor.git): "
    if not "%REPO_URL%"=="" (
        git remote add origin %REPO_URL%
    ) else (
        echo [ERROR] No repository URL provided. Aborting push.
        pause
        exit /b 1
    )
)

echo.
echo Pushing branch 'main' to origin...
git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo [SUCCESS] Repository successfully pushed to GitHub!
) else (
    echo.
    echo [NOTE] Push failed. Make sure your GitHub repository exists, is empty,
    echo and that you have authentication credentials configured (e.g., GitHub CLI 'gh auth login' or Personal Access Token).
)

pause
