@echo off
REM ---------------------------------------------------------------
REM  LinScio MedComm - Tencent Cloud Windows build server setup
REM  Run this ONCE on a fresh Windows Server to configure everything,
REM  then use scripts\build-win.bat to build.
REM
REM  Requirements before running this script:
REM    - Windows Server 2019/2022 x64
REM    - System disk at least 80 GB free, or data disk mounted
REM    - Node.js 20 LTS installed and on PATH
REM    - Python 3.11 installed and on PATH
REM    - Internet access
REM ---------------------------------------------------------------
setlocal

echo.
echo ================================================
echo   LinScio MedComm - Cloud Build Server Setup
echo ================================================
echo.

REM -- Check Node --
where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Install from:
    echo   https://nodejs.org/dist/v20.18.1/node-v20.18.1-x64.msi
    pause
    exit /b 1
)
for /f "delims=" %%v in ('node -v') do echo   Node: %%v

REM -- Check Python --
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install from:
    echo   https://www.python.org/ftp/python/3.11.11/python-3.11.11-amd64.exe
    echo   IMPORTANT: check "Add to PATH" during install
    pause
    exit /b 1
)
for /f "delims=" %%v in ('python --version') do echo   %%v

REM -- Set npm registry to China mirror --
echo.
echo [1/4] Configuring npm China mirror...
call npm config set registry https://registry.npmmirror.com
echo   npm registry: https://registry.npmmirror.com

REM -- Set Electron mirrors as system env vars --
echo.
echo [2/4] Setting Electron download mirrors...
setx ELECTRON_MIRROR https://npmmirror.com/mirrors/electron/ >nul 2>&1
setx ELECTRON_BUILDER_BINARIES_MIRROR https://npmmirror.com/mirrors/electron-builder-binaries/ >nul 2>&1
set "ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/"
set "ELECTRON_BUILDER_BINARIES_MIRROR=https://npmmirror.com/mirrors/electron-builder-binaries/"
echo   ELECTRON_MIRROR set
echo   ELECTRON_BUILDER_BINARIES_MIRROR set

REM -- Set pip China mirror --
echo.
echo [3/4] Configuring pip China mirror...
python -m pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple 2>nul
echo   pip index: https://pypi.tuna.tsinghua.edu.cn/simple

REM -- Disable Windows Defender realtime scan for build perf --
echo.
echo [4/4] Disabling Defender realtime scan for build performance...
powershell -NoProfile -Command "Set-MpPreference -DisableRealtimeMonitoring $true" 2>nul
echo   Done. Remember to re-enable after building.

echo.
echo ================================================
echo   Setup complete!
echo.
echo   IMPORTANT: Close this CMD window and open
echo   a new one so environment variables take effect.
echo.
echo   Then run:
echo     cd C:\linscio_medcomm
echo     npm install --ignore-scripts
echo     node node_modules\electron\install.js
echo     scripts\build-win.bat --no-comfyui
echo ================================================
echo.
pause
endlocal
