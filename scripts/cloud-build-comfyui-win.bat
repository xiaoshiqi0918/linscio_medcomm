@echo off
REM ================================================================
REM  LinScio MedComm - ComfyUI 组件包 Windows 打包脚本
REM  在腾讯云 Windows 服务器上运行
REM
REM  用法:
REM    scripts\cloud-build-comfyui-win.bat
REM
REM  前提:
REM    - Node.js 20+, Python 3.11, Git, curl 已安装
REM    - 40 GB 空闲磁盘
REM    - 已运行 scripts\setup-cloud-win.bat 配置镜像
REM
REM  产物:
REM    releases\v{ver}\comfyui-bundle-{comfyver}-win-x64.zip
REM    releases\v{ver}\comfyui-bundle-{comfyver}-win-x64.zip.sha256
REM ================================================================
setlocal enabledelayedexpansion

cd /d "%~dp0\.."
set "ROOT=%cd%"

for /f "delims=" %%v in ('node -p "require('./package.json').version"') do set "VER=%%v"
set "OUT_DIR=releases\v%VER%"
set "COMFY_VER=0.3.10"
set "BUNDLE_NAME=comfyui-bundle-%COMFY_VER%-win-x64"

echo.
echo ================================================================
echo   ComfyUI Bundle Build - Windows x64 - v%COMFY_VER%
echo   Output: %OUT_DIR%\%BUNDLE_NAME%.zip
echo ================================================================
echo.

REM -- 环境检测 --
echo --- 环境检测 ---
set "MISSING=0"

where node >nul 2>&1
if errorlevel 1 (
    echo [MISSING] Node.js
    set "MISSING=1"
) else (
    for /f "delims=" %%v in ('node -v') do echo [OK] Node.js %%v
)

where python >nul 2>&1
if errorlevel 1 (
    echo [MISSING] Python
    set "MISSING=1"
) else (
    for /f "delims=" %%v in ('python --version') do echo [OK] %%v
)

if "!MISSING!"=="1" (
    echo [ERROR] 缺少必要工具，请先安装
    pause
    exit /b 1
)

REM -- 磁盘空间检测 --
set "BUILDDRIVE=%ROOT:~0,1%"
powershell -NoProfile -Command "$free=(Get-PSDrive '%BUILDDRIVE%').Free; if($free -lt 30GB){Write-Host('[ERROR] 磁盘空间不足: '+[math]::Round($free/1GB,1)+'GB, 需要30GB'); exit 1}; Write-Host('[OK] 磁盘空间: '+[math]::Round($free/1GB,1)+'GB'); exit 0"
if errorlevel 1 (
    pause
    exit /b 1
)
echo.

REM -- 清理代理 --
set "HTTP_PROXY="
set "HTTPS_PROXY="
set "http_proxy="
set "https_proxy="

REM ================================================================
REM  1. 下载 ComfyUI + 模型
REM ================================================================
echo [1/4] 下载 ComfyUI + SD1.5 模型...
if exist "build\comfyui\main.py" (
    echo   ComfyUI 已存在，跳过下载
    echo   如需重新下载，删除 build\comfyui 后重试
) else (
    if not exist "node_modules" (
        echo   npm install...
        call npm install --ignore-scripts
        node node_modules\electron\install.js 2>nul
    )
    node scripts\download-comfyui.js
    if errorlevel 1 (
        echo [ERROR] ComfyUI 下载失败
        pause
        exit /b 1
    )
)

if not exist "build\comfyui\main.py" (
    echo [ERROR] build\comfyui\main.py 不存在
    pause
    exit /b 1
)

REM ================================================================
REM  2. 为 ComfyUI 创建独立 Python 环境
REM ================================================================
echo [2/4] 安装 ComfyUI Python 依赖...

if not exist "build\comfyui\python_embeded" (
    echo   创建嵌入式 Python 环境...
    python -m venv "build\comfyui\python_embeded"
)

set "COMFY_PIP=build\comfyui\python_embeded\Scripts\pip.exe"
set "COMFY_PY=build\comfyui\python_embeded\Scripts\python.exe"

echo   安装 PyTorch (CPU)...
"%COMFY_PIP%" install -i https://pypi.tuna.tsinghua.edu.cn/simple --find-links https://download.pytorch.org/whl/cpu torch torchvision torchaudio --no-warn-script-location --quiet
if errorlevel 1 (
    echo   清华镜像失败，使用 PyTorch 官方源...
    "%COMFY_PIP%" install --index-url https://download.pytorch.org/whl/cpu torch torchvision torchaudio --no-warn-script-location --quiet
)
if errorlevel 1 (
    echo [ERROR] PyTorch 安装失败
    pause
    exit /b 1
)

echo   安装 ComfyUI 其他依赖...
if exist "build\comfyui\requirements.txt" (
    "%COMFY_PIP%" install -i https://pypi.tuna.tsinghua.edu.cn/simple -r build\comfyui\requirements.txt --no-warn-script-location --quiet
) else (
    "%COMFY_PIP%" install -i https://pypi.tuna.tsinghua.edu.cn/simple einops transformers tokenizers sentencepiece safetensors aiohttp pyyaml scipy tqdm psutil kornia spandrel soundfile torchsde --no-warn-script-location --quiet
)
echo   Done.

REM ================================================================
REM  3. 打包 zip
REM ================================================================
echo [3/4] 打包 ComfyUI bundle...
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"
if exist "%OUT_DIR%\%BUNDLE_NAME%.zip" del /q "%OUT_DIR%\%BUNDLE_NAME%.zip"

set "SEVENZIP="
if exist "%ROOT%\node_modules\7zip-bin\win\x64\7za.exe" (
    set "SEVENZIP=%ROOT%\node_modules\7zip-bin\win\x64\7za.exe"
)

pushd build
if defined SEVENZIP (
    "!SEVENZIP!" a "..\%OUT_DIR%\%BUNDLE_NAME%.zip" comfyui -xr!__pycache__ -xr!.git
) else (
    powershell -NoProfile -Command "Compress-Archive -Path 'comfyui' -DestinationPath '..\%OUT_DIR%\%BUNDLE_NAME%.zip' -Force"
)
popd

if not exist "%OUT_DIR%\%BUNDLE_NAME%.zip" (
    echo [ERROR] 打包失败
    pause
    exit /b 1
)

REM ================================================================
REM  4. 生成 SHA256
REM ================================================================
echo [4/4] 生成 SHA256...
powershell -NoProfile -Command "$hash=(Get-FileHash '%OUT_DIR%\%BUNDLE_NAME%.zip' -Algorithm SHA256).Hash.ToLower(); $size=(Get-Item '%OUT_DIR%\%BUNDLE_NAME%.zip').Length; Write-Host('SHA256: '+$hash); Write-Host('Size: '+[math]::Round($size/1MB,1)+' MB'); Set-Content '%OUT_DIR%\%BUNDLE_NAME%.zip.sha256' ($hash+'  %BUNDLE_NAME%.zip')"

echo.
echo ================================================================
echo   ComfyUI Bundle 构建完成!
echo.
echo   文件: %OUT_DIR%\%BUNDLE_NAME%.zip
echo   校验: %OUT_DIR%\%BUNDLE_NAME%.zip.sha256
echo.
echo   下一步: 上传到腾讯云 COS
echo     bundles/MedComm/comfyui-basic/v%COMFY_VER%/%BUNDLE_NAME%.zip
echo ================================================================
echo.
pause
endlocal
