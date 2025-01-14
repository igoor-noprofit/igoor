@echo on
echo Starting IGOOR...
echo Activating virtual environment...
call venv\scripts\activate
echo Setting environment variables...
set "IGOOR_FULLSCREEN=True"
set "IGOOR_DEBUG=False"
set "IGOOR_ONTOP=True"
echo Starting application...

:: Launch PowerShell to minimize the window after a brief delay
start /B powershell -window minimized -Command "Start-Sleep -Seconds 2; (Get-Process -Id $PID).MainWindowHandle | ForEach-Object {$win32ShowWindow::ShowWindow($_, 6)}"

:: Start the Python application
python main.py