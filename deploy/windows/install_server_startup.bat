@echo off
REM Makes the IGOOR server start automatically at every logon, with no admin
REM rights required: a shortcut in the CURRENT USER's Startup folder points to
REM igoor_server_silent.vbs, which runs the watchdog hidden.
setlocal

powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup') + '\IGOOR Server.lnk'); $s.TargetPath='%~dp0igoor_server_silent.vbs'; $s.WorkingDirectory='%~dp0'; $s.Save()"
if errorlevel 1 (
    echo Failed to create the Startup shortcut.
    exit /b 1
)
echo Startup shortcut created: IGOOR now starts (hidden) at every logon.

echo Start it right now as well? [Y/N]
set /p ANSWER=
if /I "%ANSWER%"=="Y" cscript //nologo "%~dp0igoor_server_silent.vbs"
echo Done. To remove: run uninstall_server_startup.bat
pause
