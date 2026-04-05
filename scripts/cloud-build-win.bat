@echo off
REM ================================================================
REM  LinScio MedComm - Tencent Cloud Windows one-click build
REM
REM  This script handles EVERYTHING:
REM    1. Environment check
REM    2. Mirror configuration
REM    3. Clean source download
REM    4. npm install with native module workaround
REM    5. Full build
REM
REM  Usage:
REM    cloud-build-win.bat              (full build with ComfyUI)
REM    cloud-build-win.bat --no-comfyui (slim build, no ComfyUI)
REM    cloud-build-win.bat --skip-setup (skip env setup, just build)
REM
REM  Prereqs:
REM    - Node.js 20 LTS: https://nodejs.org/dist/v20.18.1/node-v20.18.1-x64.msi
REM    - Python 3.11:    https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
REM    - Git for Windows: https://git-scm.com/download/win
REM    - 40 GB free disk (with ComfyUI) or 10 GB (without)
REM ================================================================
setlocal enabledelayedexpansion

set "SKIP_COMFYUI=0"
set "SKIP_SETUP=0"
for %%a in (%*) do (
    if "%%a"=="--no-comfyui" set "SKIP_COMFYUI=1"
    if "%%a"=="--skip-setup" set "SKIP_SETUP=1"
)

echo.
echo ================================================================
echo   LinScio MedComm - Cloud Build - Tencent Cloud Windows
echo ================================================================
echo.

REM ================================================================
REM  PHASE 0 : Prerequisite check
REM ================================================================
echo --- Phase 0: Checking prerequisites ---
echo.

set "MISSING=0"

where node >nul 2>&1
if errorlevel 1 (
    echo [MISSING] Node.js - install from: https://nodejs.org/dist/v20.18.1/node-v20.18.1-x64.msi
    set "MISSING=1"
) else (
    for /f "delims=" %%v in ('node -v') do echo [OK] Node.js %%v
)

where python >nul 2>&1
if errorlevel 1 (
    echo [MISSING] Python - install from: https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    set "MISSING=1"
) else (
    for /f "delims=" %%v in ('python --version') do echo [OK] %%v
)

where git >nul 2>&1
if errorlevel 1 (
    echo [MISSING] Git - install from: https://git-scm.com/download/win
    set "MISSING=1"
) else (
    for /f "delims=" %%v in ('git --version') do echo [OK] %%v
)

where curl >nul 2>&1
if errorlevel 1 (
    echo [MISSING] curl - should come with Windows 10+
    set "MISSING=1"
) else (
    echo [OK] curl
)

if "!MISSING!"=="1" (
    echo.
    echo [ERROR] Install the missing tools above, then re-run this script.
    pause
    exit /b 1
)

REM -- Disk space check --
set "BUILDDRIVE=%~d0"
set "BUILDDRIVELETTER=%BUILDDRIVE:~0,1%"
set "MINGB=40"
if "%SKIP_COMFYUI%"=="1" set "MINGB=10"
powershell -NoProfile -Command "$d='%BUILDDRIVELETTER%'; $free=(Get-PSDrive $d).Free; $need=%MINGB%*1GB; if($free -lt $need){Write-Host('[ERROR] Drive '+$d+': has '+ [math]::Round($free/1GB,1) +' GB free, need '+%MINGB%+' GB'); exit 1}; Write-Host('[OK] Drive '+$d+': '+ [math]::Round($free/1GB,1) +' GB free'); exit 0"
if errorlevel 1 (
    echo.
    echo   Free up disk space before continuing.
    echo   Tips: delete C:\Users\%USERNAME%\AppData\Local\Temp\*
    echo         delete old releases\ folders
    echo         or attach a data disk and re-run from there
    pause
    exit /b 1
)

REM -- Clear broken proxy settings --
set "HTTP_PROXY="
set "HTTPS_PROXY="
set "http_proxy="
set "https_proxy="
set "ALL_PROXY="
set "all_proxy="

echo.

if "%SKIP_SETUP%"=="1" goto skip_env_setup

REM ================================================================
REM  PHASE 1 : Environment configuration (run once per server)
REM ================================================================
echo --- Phase 1: Configuring build environment ---
echo.

REM -- npm registry --
echo [1/5] Setting npm registry to China mirror...
call npm config set registry https://registry.npmmirror.com
echo   Done.

REM -- Electron mirrors (permanent env vars) --
echo [2/5] Setting Electron download mirrors...
setx ELECTRON_MIRROR "https://npmmirror.com/mirrors/electron/" >nul 2>&1
setx ELECTRON_BUILDER_BINARIES_MIRROR "https://npmmirror.com/mirrors/electron-builder-binaries/" >nul 2>&1
set "ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/"
set "ELECTRON_BUILDER_BINARIES_MIRROR=https://npmmirror.com/mirrors/electron-builder-binaries/"
echo   Done.

REM -- pip mirror --
echo [3/5] Setting pip mirror...
python -m pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple 2>nul
echo   Done.

REM -- Disable Defender realtime scan --
echo [4/5] Disabling Windows Defender realtime scan for build speed...
powershell -NoProfile -Command "try{Set-MpPreference -DisableRealtimeMonitoring $true -ErrorAction SilentlyContinue; Write-Host '  Done.'}catch{Write-Host '  Skipped (not admin or Defender not present).'}"

REM -- Clean electron-builder cache --
echo [5/5] Cleaning stale electron-builder cache...
if exist "%LOCALAPPDATA%\electron-builder\Cache\winCodeSign" (
    rmdir /s /q "%LOCALAPPDATA%\electron-builder\Cache\winCodeSign" 2>nul
    echo   Cleared winCodeSign cache.
) else (
    echo   Cache clean.
)

echo.
:skip_env_setup

REM ================================================================
REM  PHASE 2 : Get clean source code
REM ================================================================
echo --- Phase 2: Preparing source code ---
echo.

REM Detect if we are already inside the repo
if exist "package.json" (
    for /f "delims=" %%n in ('node -p "require('./package.json').name" 2^>nul') do set "PKG_NAME=%%n"
)
if "!PKG_NAME!"=="linscio-medcomm" (
    set "ROOT=%cd%"
    echo   Already in linscio_medcomm repo: !ROOT!
    goto source_ready
)

REM Not in repo - check common locations
if exist "C:\linscio_medcomm\package.json" (
    cd /d "C:\linscio_medcomm"
    set "ROOT=%cd%"
    echo   Found repo at C:\linscio_medcomm
    goto source_ready
)

REM Need to download
echo   Downloading source from GitHub...
set "DL_DIR=%~d0\linscio_medcomm"
if exist "!DL_DIR!" (
    echo   Removing old directory: !DL_DIR!
    rmdir /s /q "!DL_DIR!" 2>nul
)

REM Try mirror first, then official
curl -fSL --connect-timeout 30 -o "%~d0\medcomm.zip" "https://mirror.ghproxy.com/https://github.com/xiaoshiqi0918/linscio_medcomm/archive/refs/heads/main.zip" 2>nul
if errorlevel 1 (
    echo   Mirror failed, trying ghfast...
    curl -fSL --connect-timeout 30 -o "%~d0\medcomm.zip" "https://ghfast.top/https://github.com/xiaoshiqi0918/linscio_medcomm/archive/refs/heads/main.zip" 2>nul
)
if errorlevel 1 (
    echo   Mirrors failed, trying official GitHub...
    curl -fSL --connect-timeout 60 -o "%~d0\medcomm.zip" "https://github.com/xiaoshiqi0918/linscio_medcomm/archive/refs/heads/main.zip"
)
if errorlevel 1 (
    echo [ERROR] Failed to download source code.
    echo   Manually download from: https://github.com/xiaoshiqi0918/linscio_medcomm
    echo   and extract to %~d0\linscio_medcomm
    pause
    exit /b 1
)

echo   Extracting...
powershell -NoProfile -Command "Expand-Archive -Path '%~d0\medcomm.zip' -DestinationPath '%~d0\' -Force"
if exist "%~d0\linscio_medcomm-main" (
    move "%~d0\linscio_medcomm-main" "!DL_DIR!" >nul
)
del /q "%~d0\medcomm.zip" 2>nul
cd /d "!DL_DIR!"
set "ROOT=%cd%"
echo   Source ready at: !ROOT!

:source_ready

REM -- Clean previous build artifacts --
echo   Cleaning previous build artifacts...
if exist "releases" rmdir /s /q "releases" 2>nul
if exist "build\comfyui" rmdir /s /q "build\comfyui" 2>nul
echo   Done.
echo.

REM ================================================================
REM  PHASE 3 : npm install (with native module workaround)
REM ================================================================
echo --- Phase 3: Installing Node.js dependencies ---
echo.

REM The key insight: use --ignore-scripts to bypass:
REM   1. electron postinstall (downloads from GitHub - timeout)
REM   2. electron-builder install-app-deps (needs C++ compiler for keytar)
REM Then manually install what we need.

if exist "node_modules\.package-lock.json" (
    echo   node_modules exists, checking if usable...
    if exist "node_modules\electron\dist\electron.exe" (
        echo   node_modules OK, skipping npm install.
        goto npm_done
    ) else (
        echo   node_modules incomplete, cleaning...
        rmdir /s /q "node_modules" 2>nul
    )
)

echo   Running npm install --ignore-scripts ...
echo   This skips native module compilation that needs C++ Build Tools.
call npm install --ignore-scripts
if errorlevel 1 (
    echo [ERROR] npm install failed!
    pause
    exit /b 1
)
echo   npm packages installed.

REM -- Manually install Electron binary --
echo   Installing Electron binary from China mirror...
node node_modules\electron\install.js
if errorlevel 1 (
    echo [ERROR] Electron binary install failed!
    echo   Check ELECTRON_MIRROR env var is set.
    pause
    exit /b 1
)

if exist "node_modules\electron\dist\electron.exe" (
    echo   Electron binary OK.
) else (
    echo [ERROR] Electron binary not found after install.
    echo   Try: set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
    echo   Then re-run this script.
    pause
    exit /b 1
)

REM -- Try to rebuild keytar if C++ tools available --
where cl.exe >nul 2>&1
if not errorlevel 1 (
    echo   C++ compiler found, rebuilding native modules...
    call npx electron-builder install-app-deps 2>nul
) else (
    echo   [NOTE] No C++ compiler found - cl.exe missing.
    echo   keytar native module will not be compiled.
    echo   The app will use fallback auth storage at runtime.
    echo   To fix: install "Visual Studio Build Tools" with C++ workload.
)

:npm_done
echo.

REM ================================================================
REM  PHASE 4 : Run the actual build
REM ================================================================
echo --- Phase 4: Running build ---
echo.

if "%SKIP_COMFYUI%"=="1" (
    echo   Mode: Slim build - no ComfyUI
    call "%ROOT%\scripts\build-win.bat" --no-comfyui
) else (
    echo   Mode: Full build - with ComfyUI + SD1.5
    call "%ROOT%\scripts\build-win.bat"
)

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. Check the output above for details.
    pause
    exit /b 1
)

echo.
echo ================================================================
echo   BUILD COMPLETE!
echo.
for /f "delims=" %%v in ('node -p "require('./package.json').version"') do set "VER=%%v"
echo   Output: %ROOT%\releases\v!VER!\win-unpacked\
echo.
echo   To distribute:
echo     1. Compress win-unpacked folder to a ZIP
echo     2. Send ZIP to users
echo     3. Users extract and run LinScio MedComm.exe
echo ================================================================
echo.
pause
endlocal
