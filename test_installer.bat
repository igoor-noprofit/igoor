@echo off
setlocal enabledelayedexpansion
echo ========================================
echo Testing version extraction and InnoSetup compilation
echo ========================================
echo.

echo Step 1: Extracting version and app name from version.py...
echo ----------------------------------------
for /f "tokens=2 delims==" %%a in ('type "%~dp0version.py" ^| findstr "__version__"') do set "__version=%%a"
set "__version=%__version:"=%"
set "__version=%__version:'=%"
set "__version=%__version: =%"

for /f "tokens=2 delims==" %%a in ('type "%~dp0version.py" ^| findstr "__appname__"') do set "__appname=%%a"
set "__appname=%__appname:"=%"
set "__appname=%__appname:'=%"
set "__appname=%__appname: =%"

if "%__version%"=="" (
    echo ERROR: Could not extract version from version.py
    exit /b 1
)
echo Version extracted: %__version%
echo App name extracted: %__appname%
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

echo.
echo Running ISCC with:
echo   ISCC_PATH: !ISCC_PATH!
echo   ISS_FILE:  !ISS_FILE!
echo   MyAppVersion: "!__version!"
echo   MyAppName: "!__appname!"
echo.
echo Full command:
"!ISCC_PATH!" /DMyAppVersion="!__version!" /DMyAppName="!__appname!" "!ISS_FILE!"
echo.

"!ISCC_PATH!" /DMyAppVersion="!__version!" /DMyAppName="!__appname!" "!ISS_FILE!"
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo ERROR: InnoSetup compilation failed!
    exit /b !ERRORLEVEL!
)
echo.
echo Installer created successfully with version !__version!
echo ========================================
