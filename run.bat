@echo off
title Groww Trading Terminal
echo ========================================================
echo        Groww Algorithmic Trading Platform
echo ========================================================
echo.
echo Checking virtual environment...
if not exist "venv\Scripts\python.exe" (
    echo Virtual environment not found. Setting up...
    python -m venv venv
    call venv\Scripts\pip install -r requirements.txt
)

echo Starting Flask Server on http://127.0.0.1:5000...
echo.
start http://127.0.0.1:5000
venv\Scripts\python app.py
pause

