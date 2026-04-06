# Zip ComfyUI folder for cloud-build-comfyui-win.bat
# Avoid CMD mangling 7-Zip -xr! flags; use English-only strings (PS 5.1 + GBK default code page)
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

# 1) Built-in tar (no CMD special chars)
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
    Write-Warning 'tar failed or unsupported; falling back to 7-Zip'
}

# 2) 7-Zip via PowerShell argument arrays
if (Test-Path -LiteralPath $sevenZip) {
    if (Invoke-SevenZip) { exit 0 }
    Write-Error '7za failed (non-zero exit code)'
    exit 1
}

# 3) Last resort: larger zip, may include .git
Write-Warning 'tar and 7za unavailable; using Compress-Archive (run npm install for 7zip-bin)'
Compress-Archive -LiteralPath $SourceDir -DestinationPath $OutZip -Force
