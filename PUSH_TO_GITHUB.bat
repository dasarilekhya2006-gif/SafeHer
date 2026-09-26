@echo off
title SafeHer - Push to GitHub
cd /d "%~dp0"
echo ========================================================
echo   SafeHer - Pushing to GitHub (dasarilekhya2006-gif/SafeHer)
echo ========================================================
echo.
git push -u origin main
echo.
if %errorlevel% equ 0 (
    echo ========================================================
    echo   [SUCCESS] SafeHer has been successfully pushed!
    echo   View your repository at:
    echo   https://github.com/dasarilekhya2006-gif/SafeHer
    echo ========================================================
) else (
    echo ========================================================
    echo   Push failed or was cancelled.
    echo ========================================================
)
pause
