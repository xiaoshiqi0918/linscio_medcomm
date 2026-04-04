@echo off
REM ══════════════════════════════════════════════════════════
REM  LinScio MedComm - Windows x64 本地打包脚本
REM
REM  前置条件：
REM    1. Node.js >= 18 已安装  (node -v)
REM    2. Python 3.11 已安装    (python --version)
REM    3. Git 已安装            (git --version)
REM    4. 已在项目根目录执行过  npm install
REM
REM  用法：
REM    scripts\build-win.bat            完整构建（含 ComfyUI）
REM    scripts\build-win.bat --no-comfyui   跳过 ComfyUI 下载
REM ══════════════════════════════════════════════════════════
setlocal enabledelayedexpansion

cd /d "%~dp0\.."
set "ROOT=%cd%"

REM 读取版本号
for /f "delims=" %%v in ('node -p "require('./package.json').version"') do set "VER=%%v"
set "OUT_DIR=releases\v%VER%"

echo.
echo ══════════════════════════════════════════════
echo   LinScio MedComm v%VER% - Windows x64 Build
echo   Output: %OUT_DIR%\
echo ══════════════════════════════════════════════
echo.

REM 检查 --no-comfyui 参数
set "SKIP_COMFYUI=0"
if "%~1"=="--no-comfyui" set "SKIP_COMFYUI=1"

REM ① 下载 Windows Python wheels
echo [1/7] Downloading Python wheels (win_amd64)...
set "WHEEL_DIR=build\wheels\win32-x64"
if not exist "%WHEEL_DIR%" mkdir "%WHEEL_DIR%"

REM 生成去掉 uvicorn[standard] 的临时 requirements
powershell -Command "(Get-Content backend\requirements.txt) -replace 'uvicorn\[standard\]','uvicorn' | Set-Content build\.tmp-req-win.txt"

REM Phase 1: binary wheels
python -m pip download -r build\.tmp-req-win.txt ^
  --platform win_amd64 --python-version 3.11 ^
  --only-binary=:all: -d "%WHEEL_DIR%/" ^
  --quiet 2>nul
if errorlevel 1 (
    echo [WARN] Some binary wheels failed, trying without --only-binary...
    python -m pip download -r build\.tmp-req-win.txt -d "%WHEEL_DIR%/" --quiet 2>nul
)

REM Phase 2: sdist-only (jieba, bibtexparser)
python -m pip wheel jieba bibtexparser -w "%WHEEL_DIR%/" --quiet 2>nul
del /q "%WHEEL_DIR%\*.tar.gz" 2>nul
del /q build\.tmp-req-win.txt 2>nul

echo   Wheels ready.

REM ② 下载 Windows Python standalone
echo [2/7] Downloading Python standalone 3.11...
set "PY_TARBALL=build\python-standalone-win.tar.gz"
set "PY_URL=https://github.com/astral-sh/python-build-standalone/releases/download/20241205/cpython-3.11.11+20241205-x86_64-pc-windows-msvc-install_only.tar.gz"

if not exist "build\python\python.exe" (
    if not exist "%PY_TARBALL%" (
        echo   Downloading from GitHub...
        curl -sSL -o "%PY_TARBALL%" "%PY_URL%"
    )
    if exist "build\python" rmdir /s /q "build\python"
    tar -xzf "%PY_TARBALL%" -C build
    if not exist "build\python" (
        for /d %%d in (build\cpython-3.11*) do move "%%d" "build\python"
    )
)
echo   Python: & build\python\python.exe --version

REM ③ 预装依赖到嵌入式 Python
echo [3/7] Installing deps into embedded Python...
powershell -Command "(Get-Content backend\requirements.txt) -replace 'uvicorn\[standard\]','uvicorn' | Set-Content build\.tmp-req-win.txt"
build\python\python.exe -m pip install ^
  --no-index --find-links="%WHEEL_DIR%/" ^
  --no-warn-script-location ^
  -r build\.tmp-req-win.txt --quiet
del /q build\.tmp-req-win.txt 2>nul
echo   Done.

REM ④ Alembic 检查
echo [4/7] Alembic migration check...
cd backend
python -m alembic heads 2>nul | findstr /c:"(head)" >nul && echo   Single head OK || echo   [WARN] Multiple heads detected
cd "%ROOT%"

REM ⑤ 下载 ComfyUI + 模型（可选）
if "%SKIP_COMFYUI%"=="1" (
    echo [5/7] Skipping ComfyUI download (--no-comfyui)
) else (
    echo [5/7] Downloading ComfyUI + SD1.5 model...
    if not exist "%ROOT%\scripts\download-comfyui.js" (
        echo [ERROR] Missing: %ROOT%\scripts\download-comfyui.js
        echo   Your clone may be outdated. From project root run:
        echo     git pull origin main
        echo   Or skip ComfyUI for this build:
        echo     scripts\build-win.bat --no-comfyui
        exit /b 1
    )
    node "%ROOT%\scripts\download-comfyui.js"
    if errorlevel 1 exit /b 1
)

REM ⑥ 构建前端
echo [6/7] Building frontend...
call npm run build
if errorlevel 1 (
    echo [ERROR] Frontend build failed!
    exit /b 1
)

REM ⑦ Electron 打包
echo [7/7] Packaging with electron-builder --win --x64...
call npx electron-builder --win --x64
if errorlevel 1 (
    echo [ERROR] Electron builder failed!
    exit /b 1
)

echo.
echo ══════════════════════════════════════════════
echo   Build complete!  v%VER%
echo   Output:
echo.
dir /b "%OUT_DIR%\*.exe" 2>nul
echo.
echo   Full path: %ROOT%\%OUT_DIR%\
echo ══════════════════════════════════════════════

endlocal
