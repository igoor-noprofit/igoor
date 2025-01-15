@echo on
echo Starting IGOOR watchdog...
echo Activating virtual environment...
call venv\scripts\activate

:loop
echo Setting environment variables...
set "IGOOR_FULLSCREEN=True"
set "IGOOR_DEBUG=False"
set "IGOOR_ONTOP=False"

echo Starting application...
:: Launch PowerShell to minimize the window after a brief delay
start /B powershell -window minimized -Command "Start-Sleep -Seconds 2; (Get-Process -Id $PID).MainWindowHandle | ForEach-Object {$win32ShowWindow::ShowWindow($_, 6)}"

:: Start the Python application
python main.py

echo Application stopped or crashed. Restarting in 5 seconds...
timeout /t 5 /nobreak
goto loop