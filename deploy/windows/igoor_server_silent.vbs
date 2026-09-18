' igoor_server_silent.vbs - starts the IGOOR server watchdog with no console
' window (used by the Startup shortcut created by install_server_startup.bat).
' The watchdog .bat must sit next to this file.
Set WshShell = CreateObject("WScript.Shell")
Watchdog = Replace(WScript.ScriptFullName, "igoor_server_silent.vbs", "igoor_server_watchdog.bat")
WshShell.Run """" & Watchdog & """", 0, False
