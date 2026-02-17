@echo off
setlocal enabledelayedexpansion

rem ========================================
rem Menu: Choose build option
rem ========================================
echo ========================================
echo IGOOR Build Menu
echo ========================================
echo.
echo 1) Create only the exe file
echo 2) Create exe file AND installer
echo 3) Create both AND push to GitHub release
echo 4) Push to GitHub release only (exe and installer already exist)
echo 5) Create only the installer (skip exe build)
echo.
set /p BUILD_CHOICE="Enter your choice (1/2/3/4/5): "

if "!BUILD_CHOICE!"=="1" (
    set "CREATE_EXE=1"
    set "CREATE_INSTALLER=0"
    set "PUSH_GITHUB=0"
    goto START_BUILD
)
if "!BUILD_CHOICE!"=="2" (
    set "CREATE_EXE=1"
    set "CREATE_INSTALLER=1"
    set "PUSH_GITHUB=0"
    goto START_BUILD
)
if "!BUILD_CHOICE!"=="3" (
    set "CREATE_EXE=1"
    set "CREATE_INSTALLER=1"
    set "PUSH_GITHUB=1"
    goto START_BUILD
)
if "!BUILD_CHOICE!"=="4" (
    set "CREATE_EXE=0"
    set "CREATE_INSTALLER=0"
    set "PUSH_GITHUB=1"
    goto START_BUILD
)
if "!BUILD_CHOICE!"=="5" (
    set "CREATE_EXE=0"
    set "CREATE_INSTALLER=1"
    set "PUSH_GITHUB=0"
    goto START_BUILD
)

echo Invalid choice, aborting...
exit /b 1

:START_BUILD
echo.
echo Choice: !BUILD_CHOICE!
if "!BUILD_CHOICE!"=="1" echo Creating only the exe file...
if "!BUILD_CHOICE!"=="2" echo Creating exe file AND installer...
if "!BUILD_CHOICE!"=="3" echo Creating exe, installer, AND pushing to GitHub release...
if "!BUILD_CHOICE!"=="4" echo Pushing to GitHub release only (assuming exe and installer already exist)...
if "!BUILD_CHOICE!"=="5" echo Creating only the installer (skipping exe build)...
echo.

rem Record start time (seconds since Unix epoch) using PowerShell
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "[int][double]::Parse((Get-Date -UFormat %%s))"`) do set "__start=%%T"

if "!CREATE_EXE!"=="0" goto SKIP_BUILD

echo ========================================
echo Starting build process
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

:SKIP_BUILD

if "!CREATE_INSTALLER!"=="1" goto CREATE_INSTALLER
goto SKIP_INSTALLER

:CREATE_INSTALLER
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

:SKIP_INSTALLER
rem Record end time
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "[int][double]::Parse((Get-Date -UFormat %%s))"`) do set "__end=%%T"

rem Extract version (needed for summary even when installer is not created)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0get_version.ps1" > __version__.txt
set /p __version=<__version__.txt
del __version__.txt
if "!__version!"=="" (
    set "__version=unknown"
)

set /a __elapsed=__end - __start

rem Format elapsed seconds as HH:MM:SS
set /a __hours=__elapsed/3600
set /a __mins=(__elapsed - __hours * 3600) / 60
set /a __secs=__elapsed - __hours * 3600 - __mins * 60

rem Pad minutes and seconds
if !__mins! LSS 10 set "__mins=0!__mins!"
if !__secs! LSS 10 set "__secs=0!__secs!"

echo ========================================
echo Build process finished
echo ========================================
echo Version: !__version!
echo Elapsed time: !__hours!:!__mins!:!__secs! (HH:MM:SS) - !__elapsed! seconds

if "!BUILD_CHOICE!"=="1" echo Created: Exe file only
if "!BUILD_CHOICE!"=="2" echo Created: Exe file + Installer
if "!BUILD_CHOICE!"=="3" echo Created: Exe file + Installer + GitHub release
if "!BUILD_CHOICE!"=="4" echo Created: GitHub release only (exe and installer already exist)
if "!BUILD_CHOICE!"=="5" echo Created: Installer only (exe build skipped)
echo.

if "!PUSH_GITHUB!"=="0" goto END

echo Step 4: GitHub Release...
echo ----------------------------------------

rem Step 4.1: Token Validation
set "GITHUB_TOKEN_FILE=%~dp0.github_token.txt"
if not exist "!GITHUB_TOKEN_FILE!" (
    echo WARNING: .github_token.txt not found!
    echo.
    echo To enable GitHub releases automation:
    echo 1. Go to https://github.com/settings/tokens
    echo 2. Click "Generate new token" -^> "Generate new token (classic)"
    echo 3. Configure: Note="IGOOR Releases", Scopes=check "repo"
    echo 4. Generate and copy the token
    echo 5. Create .github_token.txt in IGOOR root and paste the token
    echo.
    set /p SKIP_GITHUB="Skip GitHub release for now? (Y/N): "
    if /i "!SKIP_GITHUB!"=="Y" (
        echo Skipping GitHub release...
        goto END
    )
    exit /b 1
)

set /p GITHUB_TOKEN=<"!GITHUB_TOKEN_FILE!"
set "GITHUB_TOKEN=!GITHUB_TOKEN: =!"
echo GitHub token found.

rem Set paths
set "INSTALLER_PATH=C:\TMP\IGOOR\DEV\INNOSETUP\RELEASES\!__version!\IGOOR-!__version!-Install-Complete.exe"
set "RELEASE_TAG=v!__version!"
set "GITHUB_API=https://api.github.com/repos/igoor-noprofit/igoor"

rem Verify installer exists
if not exist "!INSTALLER_PATH!" (
    echo ERROR: Installer not found at: !INSTALLER_PATH!
    exit /b 1
)

rem Step 4.2: Check for Existing Release
echo Checking if release !RELEASE_TAG! already exists...
curl -s -o nul -w "%%{http_code}" -H "Authorization: token !GITHUB_TOKEN!" "!GITHUB_API!/releases/tags/!RELEASE_TAG!" > __release_check__.txt
set /p RELEASE_STATUS=<__release_check__.txt
del __release_check__.txt

if "!RELEASE_STATUS!"=="200" (
    echo.
    echo Release !RELEASE_TAG! already exists!
    set /p EXISTING_ACTION="Choose action - (U)pload to existing, (S)kip, (C)ancel: "
    if /i "!EXISTING_ACTION!"=="U" (
        echo Uploading to existing release...
        goto UPLOAD_INSTALLER
    )
    if /i "!EXISTING_ACTION!"=="S" (
        echo Skipping GitHub release...
        goto END
    )
    if /i "!EXISTING_ACTION!"=="C" (
        echo Aborting...
        exit /b 1
    )
    echo Invalid choice, aborting...
    exit /b 1
)

rem Step 4.3: Create New Release
echo Creating new release !RELEASE_TAG!...
echo.
set /p RELEASE_NOTES="Enter release notes (press Enter for default): "
if "!RELEASE_NOTES!"=="" (
    set "RELEASE_NOTES=Release notes for version !__version!"
)

rem Create release JSON file
echo {> __release_data__.json
echo   "tag_name": "!RELEASE_TAG!",>> __release_data__.json
echo   "name": "IGOOR !__version!",>> __release_data__.json
echo   "body": "!RELEASE_NOTES!",>> __release_data__.json
echo   "draft": false,>> __release_data__.json
echo   "prerelease": false>> __release_data__.json
echo }>> __release_data__.json

rem Create release using curl
curl -s -X POST -H "Authorization: token !GITHUB_TOKEN!" -H "Content-Type: application/json" -d @__release_data__.json "!GITHUB_API!/releases" > __release_response__.txt
del __release_data__.json

rem Check if release was created successfully
curl -s -o nul -w "%%{http_code}" -H "Authorization: token !GITHUB_TOKEN!" "!GITHUB_API!/releases/tags/!RELEASE_TAG!" > __release_check__.txt
set /p RELEASE_STATUS=<__release_check__.txt
del __release_check__.txt

if not "!RELEASE_STATUS!"=="200" (
    echo ERROR: Failed to create release. Response:
    type __release_response__.txt
    del __release_response__.txt
    exit /b 1
)
del __release_response__.txt

echo Release !RELEASE_TAG! created successfully.

rem Step 4.4: Upload Installer
:UPLOAD_INSTALLER
echo Uploading installer...
set "INSTALLER_FILENAME=IGOOR-!__version!-Install-Complete.exe"

rem Get the upload URL for the release
curl -s -H "Authorization: token !GITHUB_TOKEN!" "!GITHUB_API!/releases/tags/!RELEASE_TAG!" > __release_info__.txt

rem Extract upload_url from JSON and properly format it using PowerShell
powershell -NoProfile -Command "$json = Get-Content __release_info__.txt | ConvertFrom-Json; $url = $json.upload_url -replace '\{.*\}', ''; Write-Output $url | Out-File -Encoding ASCII __upload_url__.txt"
set /p UPLOAD_URL=<__upload_url__.txt
del __release_info__.txt

if "!UPLOAD_URL!"=="" (
    echo ERROR: Could not retrieve upload URL
    del __upload_url__.txt 2>nul
    exit /b 1
)
del __upload_url__.txt

rem Upload the file using multipart form data
echo Uploading !INSTALLER_PATH! (this may take a while for large files)...
curl -X POST -H "Authorization: token !GITHUB_TOKEN!" -H "Content-Type: application/octet-stream" --data-binary @"!INSTALLER_PATH!" "!UPLOAD_URL!?name=!INSTALLER_FILENAME!" > __upload_response__.txt

rem Verify upload by checking the response
findstr /C:"\"state\":\"uploaded\"" __upload_response__.txt >nul
if !ERRORLEVEL! EQU 0 (
    echo Installer uploaded successfully!
    echo.
    echo Release URL: https://github.com/igoor-noprofit/igoor/releases/tag/!RELEASE_TAG!
    echo.
    echo Download URL:
    powershell -NoProfile -Command "$json = Get-Content __upload_response__.txt | ConvertFrom-Json; Write-Output $json.browser_download_url"
) else (
    echo WARNING: Upload verification failed
    echo Response from GitHub:
    type __upload_response__.txt
)
del __upload_response__.txt 2>nul

:END
echo.
