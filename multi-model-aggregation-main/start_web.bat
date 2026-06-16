@echo off
title NEXUS — Consensus AI Server
echo.
echo  ============================================
echo   NEXUS Consensus AI — Starting Web Server
echo  ============================================
echo.
echo  Opening browser at http://localhost:8000
echo  Press Ctrl+C in this window to stop the server.
echo.

:: Open browser after 2 second delay
start /b cmd /c "timeout /t 2 >nul && start http://localhost:8000"

:: Start the server (keeps running until Ctrl+C)
set PYTHONIOENCODING=utf-8
c:\Users\hp\Documents\LLM\.venv\Scripts\python.exe -m uvicorn web_app:app --reload --port 8000

pause
