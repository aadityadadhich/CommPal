@echo off
echo ===================================================
echo Starting CommPal FastAPI Backend Server (Port 8000)
echo ===================================================
cd /d "%~dp0"
set PYTHONPATH=.
backend\venv\Scripts\python.exe backend\app\db\seed.py
backend\venv\Scripts\uvicorn.exe backend.app.main:app --host 0.0.0.0 --port 8000 --reload
pause
