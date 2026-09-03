@echo off
REM IGOOR headless-server watchdog: restarts IGOOR whenever it exits.
REM Runtime mode comes from the repo .env (IGOOR_HEADLESS=true,
REM IGOOR_ACCESS_FROM_OUTSIDE=true) - this script sets nothing itself.
REM For the patient-PC (GUI, fullscreen) watchdog see igoor_watchdog.bat
REM in the repo root.
setlocal
cd /d "%~dp0..\.."

set "PYTHON=python"
if exist "venv\Scripts\python.exe" set "PYTHON=venv\Scripts\python.exe"

:loop
echo [%date% %time%] Starting IGOOR server: %PYTHON% main.py
"%PYTHON%" main.py
echo [%date% %time%] IGOOR server stopped (exit code %errorlevel%). Restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto loop
