@echo off
echo ===================================================
echo Launching CommPal (Backend + Frontend)
echo ===================================================
start "CommPal Backend (FastAPI)" run_backend.bat
start "CommPal Frontend (Next.js)" run_frontend.bat
echo Backend starting at http://localhost:8000
echo Frontend starting at http://localhost:3000
echo Check the new windows.
