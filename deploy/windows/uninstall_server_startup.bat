@echo off
REM Removes the "IGOOR Server" Startup shortcut created by
REM install_server_startup.bat (does not touch the IGOOR files themselves).
setlocal
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
if exist "%STARTUP%\IGOOR Server.lnk" (
    del "%STARTUP%\IGOOR Server.lnk"
    echo Startup shortcut removed - IGOOR will no longer auto-start at logon.
) else (
    echo Startup shortcut not found - nothing to remove.
)
pause
