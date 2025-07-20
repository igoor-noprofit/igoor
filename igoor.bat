@echo on
echo Starting IGOOR...
echo Activating virtual environment...
call venv\scripts\activate

:loop
echo Setting environment variables...
set "IGOOR_FULLSCREEN=False"
set "IGOOR_DEBUG=True"
set "IGOOR_ONTOP=False"

echo Starting application...
:: Launch PowerShell to minimize the window after a brief delay
start /B powershell -window minimized -Command  "(Get-Process -Id $PID).MainWindowHandle | ForEach-Object { Add-Type -Name Window -Namespace Console -MemberDefinition '[DllImport(\"user32.dll\")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);'; [Console.Window]::ShowWindow($_, 2) }"

:: Start the Python application
python main.py