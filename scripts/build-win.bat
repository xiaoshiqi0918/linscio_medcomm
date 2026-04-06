@echo off
REM ---------------------------------------------------------------
REM  LinScio MedComm  -  Windows x64 客户端本地打包脚本
REM  分包模式（v0.2+）：此脚本仅打包瘦客户端（不含 ComfyUI）
REM  ComfyUI 组件包请用 scripts\cloud-build-comfyui-win.bat
REM
REM  Run from repo root:  scripts\build-win.bat
REM
REM  Prereqs: Git, Node 18+, Python 3.11, curl, tar
REM           npm install at repo root beforehand
REM  Disk   : ~8 GB free
REM  Output : releases\v<ver>\LinScio-MedComm-<ver>-win-x64.exe
REM
REM  Env overrides for Python standalone download:
REM    MEDCOMM_PY_STANDALONE_URL  - single custom URL
REM    MEDCOMM_PY_SKIP_MIRROR=1  - skip CN mirrors
REM ---------------------------------------------------------------
setlocal enabledelayedexpansion

cd /d "%~dp0\.."
set "ROOT=%cd%"

for /f "delims=" %%v in ('node -p "require('./package.json').version"') do set "VER=%%v"
set "OUT_DIR=releases\v%VER%"

echo.
echo ==============================================
echo   LinScio MedComm v%VER% - Windows x64 Build
echo   Output: %OUT_DIR%\
echo ==============================================
echo.

REM 分包模式：客户端构建始终不含 ComfyUI
set "SKIP_COMFYUI=1"

REM == Disk space pre-check ======================================
set "BUILDDRIVE=%ROOT:~0,1%"
set "MINGB=8"
powershell -NoProfile -Command "$need=[int]$env:MINGB; if((Get-PSDrive $env:BUILDDRIVE).Free -lt $need*1GB){exit 1};exit 0"
if not errorlevel 1 goto diskcheck_ok
echo [ERROR] Drive %BUILDDRIVE%: has less than %MINGB% GB free.
echo   Free up space or move repo to a larger disk, then retry.
pause
exit /b 1
:diskcheck_ok

REM == Clear proxy if set but unreachable =========================
set "HTTP_PROXY="
set "HTTPS_PROXY="
set "http_proxy="
set "https_proxy="
set "ALL_PROXY="
set "all_proxy="

REM == 1/7  Python wheels ========================================
echo [1/7] Downloading Python wheels...
set "WHEEL_DIR=build\wheels\win32-x64"
if not exist "%WHEEL_DIR%" mkdir "%WHEEL_DIR%"
if not exist "build" mkdir "build"

python -c "from pathlib import Path; Path('build').mkdir(exist_ok=True); t=Path('backend/requirements.txt').read_text(encoding='utf-8'); Path('build/.tmp-req-win.txt').write_text(t.replace('uvicorn[standard]','uvicorn'), encoding='utf-8')"
if errorlevel 1 (
    echo [ERROR] Could not create build\.tmp-req-win.txt - is Python on PATH?
    pause
    exit /b 1
)

python -m pip download -r build\.tmp-req-win.txt -d "%WHEEL_DIR%/" --quiet
if errorlevel 1 (
    echo [WARN] Some wheels failed, retrying with platform flag...
    python -m pip download -r build\.tmp-req-win.txt --platform win_amd64 --python-version 3.11 --only-binary=:all: -d "%WHEEL_DIR%/" --quiet 2>nul
)

python -m pip wheel jieba bibtexparser -w "%WHEEL_DIR%/" --quiet 2>nul
del /q "%WHEEL_DIR%\*.tar.gz" 2>nul
del /q build\.tmp-req-win.txt 2>nul
echo   Wheels ready.

REM == 2/7  Embedded Python ======================================
echo [2/7] Downloading Python standalone 3.11...
set "PY_TARBALL=build\python-standalone-win.tar.gz"
set "PY_TAG=20241205"
set "PY_FN=cpython-3.11.11+%PY_TAG%-x86_64-pc-windows-msvc-install_only.tar.gz"
set "PY_REL=github.com/astral-sh/python-build-standalone/releases/download/%PY_TAG%/%PY_FN%"
set "PY_URL_OFFICIAL=https://%PY_REL%"
set "PY_URL_M1=https://mirror.ghproxy.com/https://%PY_REL%"
set "PY_URL_M2=https://ghfast.top/https://%PY_REL%"

if exist "build\python\python.exe" goto py_ready

set "PY_ROUND=0"
:py_retry
set /a PY_ROUND+=1
if !PY_ROUND! gtr 3 (
    echo [ERROR] Failed to obtain embedded Python after 3 rounds.
    echo   Try deleting %ROOT%\%PY_TARBALL% and re-running.
    pause
    exit /b 1
)

if exist "%PY_TARBALL%" (
    tar -tzf "%PY_TARBALL%" >nul 2>&1
    if errorlevel 1 (
        echo [WARN] Tarball corrupt - deleting...
        del /q "%PY_TARBALL%" 2>nul
    )
)
if exist "%PY_TARBALL%" goto py_extract

echo   Downloading tarball...
del /q "%PY_TARBALL%.part" 2>nul
set "PY_SI=0"
:py_next_src
set /a PY_SI+=1
if defined MEDCOMM_PY_STANDALONE_URL goto py_pick_custom
if "%MEDCOMM_PY_SKIP_MIRROR%"=="1" goto py_pick_official
goto py_pick_mirrors

:py_pick_custom
if !PY_SI! gtr 1 goto py_sources_exhausted
set "PY_CUR=!MEDCOMM_PY_STANDALONE_URL!"
goto py_do_curl
:py_pick_official
if !PY_SI! gtr 1 goto py_sources_exhausted
set "PY_CUR=!PY_URL_OFFICIAL!"
goto py_do_curl
:py_pick_mirrors
if !PY_SI! equ 1 set "PY_CUR=!PY_URL_M1!"
if !PY_SI! equ 2 set "PY_CUR=!PY_URL_M2!"
if !PY_SI! equ 3 set "PY_CUR=!PY_URL_OFFICIAL!"
if !PY_SI! gtr 3 goto py_sources_exhausted
goto py_do_curl

:py_do_curl
echo   Source: !PY_CUR!
curl -fSL --connect-timeout 60 --retry 3 --retry-delay 4 -o "%PY_TARBALL%.part" "!PY_CUR!"
if not errorlevel 1 goto py_curl_ok
echo   [WARN] Download failed, trying next...
del /q "%PY_TARBALL%.part" 2>nul
goto py_next_src

:py_curl_ok
set "PY_SZ=0"
for %%A in ("%PY_TARBALL%.part") do set "PY_SZ=%%~zA"
if !PY_SZ! lss 5000000 (
    echo   [WARN] File too small, trying next source...
    del /q "%PY_TARBALL%.part" 2>nul
    goto py_next_src
)
move /y "%PY_TARBALL%.part" "%PY_TARBALL%" >nul
tar -tzf "%PY_TARBALL%" >nul 2>&1
if not errorlevel 1 goto py_extract
echo   [WARN] Invalid gzip, trying next source...
del /q "%PY_TARBALL%" 2>nul
goto py_next_src

:py_sources_exhausted
echo   [WARN] All sources failed this round.
del /q "%PY_TARBALL%.part" 2>nul
goto py_retry

:py_extract
if exist "build\python" rmdir /s /q "build\python"
for /d %%d in (build\cpython-3.11*) do rmdir /s /q "%%d" 2>nul
tar -xzf "%PY_TARBALL%" -C build
if errorlevel 1 (
    echo   [WARN] Extract failed - re-downloading...
    del /q "%PY_TARBALL%" 2>nul
    goto py_retry
)
if not exist "build\python" (
    for /d %%d in (build\cpython-3.11*) do move "%%d" "build\python"
)
if not exist "build\python\python.exe" (
    echo   [WARN] python.exe missing after extract - re-downloading...
    del /q "%PY_TARBALL%" 2>nul
    if exist "build\python" rmdir /s /q "build\python"
    goto py_retry
)

:py_ready
if not exist "build\python\python.exe" (
    echo [ERROR] Embedded Python missing at build\python\python.exe
    pause
    exit /b 1
)
echo   Python:
build\python\python.exe --version

REM == 3/7  Install deps into embedded Python ====================
echo [3/7] Installing deps into embedded Python...
python -c "from pathlib import Path; Path('build').mkdir(exist_ok=True); t=Path('backend/requirements.txt').read_text(encoding='utf-8'); Path('build/.tmp-req-win.txt').write_text(t.replace('uvicorn[standard]','uvicorn'), encoding='utf-8')"
build\python\python.exe -m pip install --no-index --find-links="%WHEEL_DIR%/" --no-warn-script-location -r build\.tmp-req-win.txt --quiet 2>nul
if errorlevel 1 (
    echo   [WARN] Local wheels incomplete, installing from PyPI mirror...
    build\python\python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --find-links="%WHEEL_DIR%/" --no-warn-script-location -r build\.tmp-req-win.txt --quiet
    if errorlevel 1 (
        echo [ERROR] Failed to install Python dependencies!
        del /q build\.tmp-req-win.txt 2>nul
        pause
        exit /b 1
    )
)
del /q build\.tmp-req-win.txt 2>nul
echo   Done.

REM == 4/7  ComfyUI Python deps ====================================
if "%SKIP_COMFYUI%"=="1" (
    echo [4/7] Skipping ComfyUI deps per --no-comfyui flag
) else (
    echo [4/7] Installing ComfyUI deps into embedded Python...
    echo   Installing PyTorch CPU for Windows...
    build\python\python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --find-links https://download.pytorch.org/whl/cpu torch torchvision torchaudio --no-warn-script-location --quiet
    if errorlevel 1 (
        echo   [WARN] Tuna mirror failed, trying PyTorch official index...
        build\python\python.exe -m pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision torchaudio --no-warn-script-location --quiet
    )
    if errorlevel 1 (
        echo [ERROR] Failed to install PyTorch!
        pause
        exit /b 1
    )
    echo   Installing remaining ComfyUI requirements...
    if exist "build\comfyui\requirements.txt" (
        build\python\python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --no-warn-script-location -r build\comfyui\requirements.txt --quiet
    ) else (
        build\python\python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --no-warn-script-location einops transformers tokenizers sentencepiece safetensors aiohttp pyyaml scipy tqdm psutil kornia spandrel soundfile torchsde --quiet
    )
    if errorlevel 1 (
        echo [ERROR] Failed to install ComfyUI dependencies!
        pause
        exit /b 1
    )
    echo   Done.
)

REM == 4b/7  Alembic check ========================================
echo   Alembic migration check...
pushd "%ROOT%\backend"
python -m alembic heads 2>nul
popd

REM == 5/7  ComfyUI + SD1.5 =====================================
if "%SKIP_COMFYUI%"=="1" (
    echo [5/7] Skipping ComfyUI per --no-comfyui flag
) else (
    echo [5/7] Downloading ComfyUI + SD1.5 model...
    if not exist "%ROOT%\scripts\download-comfyui.js" (
        echo [ERROR] scripts\download-comfyui.js not found
        echo   Run: git pull origin main
        echo   Or:  scripts\build-win.bat --no-comfyui
        pause
        exit /b 1
    )
    node "%ROOT%\scripts\download-comfyui.js"
    if errorlevel 1 (
        pause
        exit /b 1
    )
)

REM == 6/7  Frontend build =======================================
echo [6/7] Building frontend...
call npm run build
if errorlevel 1 (
    echo [ERROR] Frontend build failed!
    pause
    exit /b 1
)

REM == 7/7  Electron packaging ===================================
echo [7/7] Packaging with electron-builder --win --x64...
set SKIP_COMFYUI_PACK=1
call npx electron-builder --win --x64
if errorlevel 1 (
    echo [ERROR] Electron builder failed!
    pause
    exit /b 1
)

set "EXE_NAME=LinScio-MedComm-%VER%-win-x64.exe"

echo.
echo ==============================================
echo   Build complete v%VER%
echo.
if exist "%OUT_DIR%\%EXE_NAME%" (
    echo   Installer: %OUT_DIR%\%EXE_NAME%
    echo   Upload this .exe to COS for distribution.
) else (
    echo   [WARN] Installer .exe not found, check electron-builder output.
    dir "%OUT_DIR%\*.exe" 2>nul
)
echo ==============================================
echo.
pause
endlocal
