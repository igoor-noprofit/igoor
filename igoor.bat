@echo on
rem igoor.bat - launch IGOOR detached to avoid lingering cmd holding sockets
echo Starting IGOOR (detached)...

rem Set environment variables that the app expects
set "IGOOR_FULLSCREEN=False"
set "IGOOR_DEBUG=True"
set "IGOOR_ONTOP=False"

rem -- Optional: brutally kill any process listening on the websockets port (9715)
rem This helps avoid "address already in use" when restarting quickly.
for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":9715"') do (
	echo Found process listening on port 9715: PID %%A
	echo Killing PID %%A ...
	taskkill /PID %%A /F >nul 2>&1
)

rem Use the venv python executable directly so we don't need to "activate" the venv in this cmd.
rem Start the app detached and minimized, then exit this script so the cmd window closes immediately.
set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
	echo Virtualenv python not found at "%PYTHON_EXE%". Falling back to system python.
	set "PYTHON_EXE=python"
)

echo Launching: "%PYTHON_EXE%" "%~dp0main.py"
start "IGOOR" /MIN "%PYTHON_EXE%" "%~dp0main.py"

rem Exit this batch immediately so the original cmd window does not linger.
exit /B 0