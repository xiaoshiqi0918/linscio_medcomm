# ComfyUI 目录打 zip（供 cloud-build-comfyui-win.bat 调用）
# 不在 CMD 里拼 -xr!，避免 setlocal enabledelayedexpansion 破坏 7-Zip 参数
param(
    [Parameter(Mandatory)][string]$OutZip,
    [Parameter(Mandatory)][string]$SourceDir
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $SourceDir)) {
    Write-Error "Source not found: $SourceDir"
    exit 1
}
$parent = Split-Path -LiteralPath $SourceDir -Parent
$name = Split-Path -LiteralPath $SourceDir -Leaf
$repoRoot = Split-Path $PSScriptRoot -Parent
$sevenZip = Join-Path $repoRoot 'node_modules\7zip-bin\win\x64\7za.exe'
$outFull = [System.IO.Path]::GetFullPath($OutZip)

function Invoke-SevenZip {
    Push-Location $parent
    try {
        & $sevenZip @('a', $outFull, $name, '-xr!__pycache__', '-xr!.git')
        return ($LASTEXITCODE -eq 0)
    } finally {
        Pop-Location
    }
}

# 1) Windows 自带 tar（无 CMD 特殊字符问题）
if (Get-Command tar -ErrorAction SilentlyContinue) {
    Push-Location $parent
    try {
        & tar -a -c -f $outFull --exclude='.git' --exclude='__pycache__' $name
        $ok = ($LASTEXITCODE -eq 0)
    } finally {
        Pop-Location
    }
    if ($ok -and (Test-Path -LiteralPath $outFull)) {
        exit 0
    }
    Write-Warning "tar 打包失败或不支持，改用 7-Zip..."
}

# 2) 7-Zip（参数在 PowerShell 中传递，-xr! 不会被 CMD 解析）
if (Test-Path -LiteralPath $sevenZip) {
    if (Invoke-SevenZip) { exit 0 }
    Write-Error "7za failed (exit code was non-zero)"
    exit 1
}

# 3) 兜底
Write-Warning 'tar/7za 不可用，使用 Compress-Archive（体积更大、可能含 .git，建议 npm install）'
Compress-Archive -LiteralPath $SourceDir -DestinationPath $OutZip -Force
