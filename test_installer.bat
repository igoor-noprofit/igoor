@echo off
setlocal enabledelayedexpansion
echo ========================================
echo Testing version extraction and InnoSetup compilation
echo ========================================
echo.

echo Step 1: Extracting version from version.py...
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

echo Step 2: Creating installer with InnoSetup...
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
echo.
echo Installer created successfully with version !__version!
echo ========================================
