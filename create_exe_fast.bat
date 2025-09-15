@echo off
rem Record start time (seconds since Unix epoch) using PowerShell
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "[int][double]::Parse((Get-Date -UFormat %%s))"`) do set "__start=%%T"

echo Starting build at %date% %time%

copy /Y igoor.spec.txt igoor.spec
pyinstaller igoor.spec --noconfirm

rem Record end time
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "[int][double]::Parse((Get-Date -UFormat %%s))"`) do set "__end=%%T"

set /a __elapsed=__end - __start

rem Format elapsed seconds as HH:MM:SS (avoid %% modulus operator which can break parsing in batch)
set /a __hours=__elapsed/3600
set /a __mins=(__elapsed - __hours * 3600) / 60
set /a __secs=__elapsed - __hours * 3600 - __mins * 60

rem Pad minutes and seconds
if %__mins% LSS 10 set "__mins=0%__mins%"
if %__secs% LSS 10 set "__secs=0%__secs%"

echo Build finished at %date% %time%
echo Elapsed time: %__hours%:%__mins%:%__secs% (HH:MM:SS) - %__elapsed% seconds