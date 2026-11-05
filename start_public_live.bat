@echo off
title Day Trader Terminal - Live Mobile & Remote Server
echo ========================================================
echo       Starting Day Trader Terminal + Live Public Tunnel
echo ========================================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo Setting up virtual environment...
    python -m venv venv
    call venv\Scripts\pip install -r requirements.txt
)

echo 1. Starting Flask server in background...
start /b venv\Scripts\python app.py

echo 2. Launching Cloudflare Live Tunnel...
timeout /t 3 /nobreak >nul

venv\Scripts\python tunnel_launcher.py
pause

