@echo off
title BisaRx Server
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Virtual environment not found at .venv\Scripts\python.exe
  echo Create it and install requirements.txt first.
  pause
  exit /b 1
)

echo ============================================================
echo   BisaRx - Starting server...
echo   Browser will open automatically in a few seconds.
echo   Close this window to stop the server.
echo ============================================================
echo.

start "" /b cmd /c "timeout /t 3 >nul & start """" http://127.0.0.1:8001"

".venv\Scripts\python.exe" main.py

echo.
echo ============================================================
echo   Server stopped. Press any key to close.
echo ============================================================
pause >nul
