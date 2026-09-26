@echo off
title SafeHer - Women Safety Backend Server
color 0A
cd /d "%~dp0"

echo.
echo  ==============================================
echo    SafeHer Women Safety Route Navigation
echo  ==============================================
echo.

set PYTHON_CMD=C:\Python314\python.exe

echo  Using Python: %PYTHON_CMD%
echo.

echo [1/3] Installing all dependencies (Flask + ML libraries)...
%PYTHON_CMD% -m pip install Flask Flask-Cors requests scikit-learn numpy pandas joblib -q
echo.

echo [2/3] Training ML Risk Classifier (first-time setup)...
%PYTHON_CMD% ml_trainer.py
echo.

echo [3/3] Starting SafeHer server...
echo.
echo  Open your browser at:  http://127.0.0.1:5000
echo  Press Ctrl+C to stop the server.
echo.

%PYTHON_CMD% app.py

echo.
echo  Server stopped. Press any key to close.
pause >nul
