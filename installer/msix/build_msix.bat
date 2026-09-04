@echo off
setlocal enabledelayedexpansion

rem ========================================
rem Build an MSIX package from the PyInstaller onedir output.
rem
rem Usage: build_msix.bat [cert_thumbprint]
rem   1. Run create_exe.bat first (needs dist\igoor\igoor.exe)
rem   2. Optional: pass a certificate thumbprint to sign the .msix
rem      with signtool after packaging (e.g. the self-signed test cert).
rem ========================================

set "SDK_BIN=C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64"
set "HERE=%~dp0"
set "ROOT=%HERE%..\.."
set "DIST=%ROOT%\dist\igoor"
set "LAYOUT=%HERE%layout"

if not exist "!SDK_BIN!\makeappx.exe" (
    echo ERROR: makeappx.exe not found at: !SDK_BIN!
    exit /b 1
)

if not exist "!DIST!\igoor.exe" (
    echo ERROR: !DIST!\igoor.exe not found - run create_exe.bat first
    exit /b 1
)

rem Extract version from version.py (get_version.ps1 writes to stderr, so parse directly)
for /f "tokens=2 delims== " %%V in ('findstr /b "__version__" "!ROOT!\version.py"') do set "__version=%%V"
set "__version=!__version:\"=!"
set "__version=!__version:'=!"
if "!__version!"=="" (
    echo ERROR: Could not extract version from version.py
    exit /b 1
)

rem MSIX versions are 4-part (pad 1.1.0 -> 1.1.0.0)
for /f "usebackq delims=" %%V in (`powershell -NoProfile -Command "$p=@('!__version!'.Split('.')); while($p.Count -lt 4){$p+='0'}; $p[0..3] -join '.'"`) do set "PKG_VERSION=%%V"
echo Version: !PKG_VERSION!

echo Copying build output into layout...
robocopy "!DIST!" "!LAYOUT!" /E /NFL /NDL /NJH /NJS /NP >nul
if !ERRORLEVEL! GEQ 8 (
    echo ERROR: robocopy of dist failed
    exit /b 1
)
copy /Y "!HERE!AppxManifest.xml" "!LAYOUT!\AppxManifest.xml" >nul
robocopy "!HERE!assets" "!LAYOUT!\assets" /E /NFL /NDL /NJH /NJS /NP >nul

rem The repo .env carries dev flags (headless/external access/debug) - ship the
rem production one instead. Inno Setup rewrites .env at install time; MSIX
rem cannot, so the package must already contain the right defaults.
copy /Y "!HERE!env.production" "!LAYOUT!\_internal\.env" >nul

echo Packaging with makeappx (a few minutes for ~1.2 GB)...
"!SDK_BIN!\makeappx.exe" pack /h SHA256 /d "!LAYOUT!" /p "!HERE!IGOOR-!PKG_VERSION!.msix"
if !ERRORLEVEL! NEQ 0 (
    echo ERROR: makeappx failed
    exit /b !ERRORLEVEL!
)
set "MSIX=!HERE!IGOOR-!PKG_VERSION!.msix"
echo Created: !MSIX!

if "%~1"=="" goto END

echo Signing with certificate thumbprint %~1 ...
"!SDK_BIN!\signtool.exe" sign /fd SHA256 /sha1 %~1 "!MSIX!"
if !ERRORLEVEL! NEQ 0 (
    echo ERROR: signtool sign failed
    exit /b !ERRORLEVEL!
)
"!SDK_BIN!\signtool.exe" verify /pa "!MSIX!"
if !ERRORLEVEL! NEQ 0 (
    echo ERROR: signature verification failed
    exit /b !ERRORLEVEL!
)
echo Signed and verified.

:END
endlocal
