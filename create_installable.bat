@echo off
setlocal enabledelayedexpansion
rem Record start time (seconds since Unix epoch) using PowerShell
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "[int][double]::Parse((Get-Date -UFormat %%s))"`) do set "__start=%%T"

echo ========================================
echo Starting complete build and installer creation
echo ========================================
echo.

echo Step 1: Building executable with PyInstaller...
echo ----------------------------------------
call create_exe.bat
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo ERROR: PyInstaller build failed!
    echo Aborting installer creation.
    exit /b !ERRORLEVEL!
)
echo PyInstaller build completed successfully.
echo.

echo Step 2: Extracting version from version.py...
echo ----------------------------------------
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0get_version.ps1" > __version__.txt
set /p __version=<__version__.txt
del __version__.txt
if "!__version!"=="" (
    echo ERROR: Could not extract version from version.py
    exit /b 1
)
echo Version extracted: !__version!
echo.

echo Step 3: Creating installer with InnoSetup...
echo ----------------------------------------
set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
set "ISS_FILE=C:\TMP\IGOOR\DEV\INNOSETUP\igoor_setup\igoor.iss"

if not exist "!ISCC_PATH!" (
    echo ERROR: InnoSetup compiler not found at: !ISCC_PATH!
    exit /b 1
)

if not exist "!ISS_FILE!" (
    echo ERROR: InnoSetup script not found at: !ISS_FILE!
    exit /b 1
)

"!ISCC_PATH!" /DMyAppVersion="!__version!" "!ISS_FILE!"
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo ERROR: InnoSetup compilation failed!
    exit /b !ERRORLEVEL!
)
echo Installer created successfully.
echo.

rem Record end time
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "[int][double]::Parse((Get-Date -UFormat %%s))"`) do set "__end=%%T"

set /a __elapsed=__end - __start

rem Format elapsed seconds as HH:MM:SS
set /a __hours=__elapsed/3600
set /a __mins=(__elapsed - __hours * 3600) / 60
set /a __secs=__elapsed - __hours * 3600 - __mins * 60

rem Pad minutes and seconds
if !__mins! LSS 10 set "__mins=0!__mins!"
if !__secs! LSS 10 set "__secs=0!__secs!"

echo ========================================
echo Complete build and installer creation finished
echo ========================================
echo Version: !__version!
echo Elapsed time: !__hours!:!__mins!:!__secs! (HH:MM:SS) - !__elapsed! seconds
echo.
