# update-llamacpp-win-cuda.ps1
# Downloads the latest llama.cpp CUDA Windows release from GitHub and
# replaces the binaries in backend/artifacts/llama-cpp/cuda/bin/
#
# Usage (from repo root or backend/):
#   .\scripts\dev\backend\update-llamacpp-win-cuda.ps1
#   .\scripts\dev\backend\update-llamacpp-win-cuda.ps1 -CudaVersion 12.1
#   .\scripts\dev\backend\update-llamacpp-win-cuda.ps1 -DryRun

param(
    [string]$CudaVersion = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Write-Status  { Write-Host "[INFO]  $args" -ForegroundColor Cyan }
function Write-Ok      { Write-Host "[OK]    $args" -ForegroundColor Green }
function Write-Warn    { Write-Host "[WARN]  $args" -ForegroundColor Yellow }
function Write-Fail    { param($msg) Write-Host "[ERROR] $msg" -ForegroundColor Red; exit 1 }

# Resolve bin directory
$currentDir = (Get-Item .).Name
if ($currentDir -eq "backend") {
    $binDir = ".\artifacts\llama-cpp\cuda\bin"
} elseif (Test-Path ".\backend\artifacts\llama-cpp\cuda\bin") {
    $binDir = ".\backend\artifacts\llama-cpp\cuda\bin"
} else {
    Write-Fail "Run this script from the repo root or backend/ directory."
}
$binDir = (Resolve-Path $binDir).Path
Write-Status "Target bin dir: $binDir"

# Detect current binary build number
$serverExe = Join-Path $binDir "llama-server.exe"
$currentBuild = 0
if (Test-Path $serverExe) {
    # Capture all output (stdout + stderr merged) and ignore non-zero exit
    $versionOutput = cmd /c "`"$serverExe`" --version 2>&1"
    $versionLine = $versionOutput | Where-Object { $_ -match "version:" } | Select-Object -First 1
    if ($versionLine -match "version:\s*(\d+)") {
        $currentBuild = [int]$matches[1]
        Write-Status "Current build: b$currentBuild"
    }
} else {
    Write-Warn "llama-server.exe not found - will do a fresh install."
}

# Auto-detect CUDA version from CUDA_PATH (most reliable on Windows)
if ([string]::IsNullOrEmpty($CudaVersion)) {
    if ($env:CUDA_PATH -match "v(\d+\.\d+)") {
        $CudaVersion = $matches[1]
        Write-Status "CUDA version from CUDA_PATH: $CudaVersion"
    }
}

# Fallback: try nvcc (use cmd to avoid PowerShell treating stderr as error)
if ([string]::IsNullOrEmpty($CudaVersion)) {
    $nvccOut = cmd /c "nvcc --version 2>&1"
    if ($nvccOut -match "release (\d+\.\d+)") {
        $CudaVersion = $matches[1]
        Write-Status "CUDA version from nvcc: $CudaVersion"
    }
}

if ([string]::IsNullOrEmpty($CudaVersion)) {
    $CudaVersion = "12.4"
    Write-Warn "Could not detect CUDA version - defaulting to $CudaVersion. Pass -CudaVersion X.Y to override."
}

# Strip any leading "v" or "cu" to get a plain "12.4" string for matching
$CudaVersion = $CudaVersion -replace "^[vcu]+"
Write-Status "Looking for CUDA version: $CudaVersion"

# Fetch latest release from GitHub API
Write-Status "Fetching latest llama.cpp release from GitHub API..."
$headers = @{ "User-Agent" = "erudi-updater" }
if ($env:GH_TOKEN) {
    $headers["Authorization"] = "Bearer $env:GH_TOKEN"
}

try {
    $release = Invoke-RestMethod `
        -Uri "https://api.github.com/repos/ggerganov/llama.cpp/releases/latest" `
        -Headers $headers
} catch {
    Write-Fail "GitHub API request failed: $_"
}

$latestBuild = 0
if ($release.tag_name -match "b(\d+)") {
    $latestBuild = [int]$matches[1]
}
Write-Status "Latest release: $($release.tag_name) (build b$latestBuild)"

if ($latestBuild -le $currentBuild -and $currentBuild -gt 0) {
    Write-Ok "Already up to date (b$currentBuild). Nothing to do."
    exit 0
}

# Find matching asset
# llama.cpp has used two naming conventions over time:
#   old: llama-bXXXX-bin-win-cuda-cu12.1-x64.zip
#   new: llama-b8739-bin-win-cuda-12.4-x64.zip
$asset = $release.assets | Where-Object {
    ($_.name -like "*win*cuda*${CudaVersion}*x64*.zip") -or
    ($_.name -like "*win*cuda*cu${CudaVersion}*x64*.zip")
} | Select-Object -First 1

if (-not $asset) {
    # Fall back to highest available CUDA 12.x build
    Write-Warn "No asset for CUDA $CudaVersion - picking highest available CUDA 12.x build..."
    $asset = $release.assets | Where-Object {
        ($_.name -like "*win*cuda*12.*x64*.zip") -or
        ($_.name -like "*win*cuda*cu12*x64*.zip")
    } | Sort-Object { $_.name } -Descending | Select-Object -First 1
}

if (-not $asset) {
    Write-Status "Available assets in this release:"
    $release.assets | ForEach-Object { Write-Host "  $($_.name)" }
    Write-Fail "No matching CUDA Windows asset found. Check the list above."
}

$assetSizeMB = [math]::Round($asset.size / 1048576, 1)
$assetLabel = "$($asset.name) - $assetSizeMB MB"
Write-Status "Found asset: $assetLabel"

if ($DryRun) {
    Write-Ok "DRY RUN - would download: $($asset.name)"
    Write-Ok "DRY RUN - target: $binDir"
    exit 0
}

# Download
$tmpDir  = Join-Path $env:TEMP "llama-cpp-update-$(Get-Random)"
$zipPath = Join-Path $tmpDir "llama-cpp.zip"
New-Item -ItemType Directory -Path $tmpDir | Out-Null

Write-Status "Downloading... (this may take a few minutes)"
try {
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zipPath -UseBasicParsing
} catch {
    Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Fail "Download failed: $_"
}
Write-Ok "Download complete."

# Extract
$extractDir = Join-Path $tmpDir "extracted"
Write-Status "Extracting archive..."
Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

# Find EXEs (some zips have a nested folder, some don't)
$exeFiles = Get-ChildItem -Path $extractDir -Filter "*.exe" -Recurse
if (-not $exeFiles) {
    Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Fail "No .exe files found in the downloaded archive."
}
$extractedBinDir = $exeFiles[0].DirectoryName
Write-Status "Extracted to: $extractedBinDir"

# Check for Gemma 4 support in the new binary
$newServer = Join-Path $extractedBinDir "llama-server.exe"
if (Test-Path $newServer) {
    $binaryContent = [System.IO.File]::ReadAllText($newServer)
    if ($binaryContent -match "gemma4") {
        Write-Ok "Gemma 4 architecture confirmed in new binary."
    } else {
        Write-Warn "gemma4 string not found - Gemma 4 may not be supported in this build yet."
        $confirm = Read-Host "Install anyway? [y/N]"
        if ($confirm -notmatch "^[Yy]") {
            Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
            Write-Status "Aborted."
            exit 0
        }
    }
}

# Backup current binaries
if ($currentBuild -gt 0) {
    $backupDir = Join-Path (Split-Path $binDir) "bin-backup-b$currentBuild"
    if (-not (Test-Path $backupDir)) {
        Write-Status "Backing up current binaries to bin-backup-b$currentBuild..."
        Copy-Item -Path $binDir -Destination $backupDir -Recurse
        Write-Ok "Backup done."
    }
}

# Replace EXEs and DLLs (preserve Python scripts and gguf-py folder)
Write-Status "Replacing binaries..."

Get-ChildItem -Path $extractedBinDir -Filter "*.exe" | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination (Join-Path $binDir $_.Name) -Force
}
Get-ChildItem -Path $extractedBinDir -Filter "*.dll" -ErrorAction SilentlyContinue | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination (Join-Path $binDir $_.Name) -Force
}

# Verify
$verifyOutput = cmd /c "`"$serverExe`" --version 2>&1" | Where-Object { $_ -match "version:" }
Write-Ok "Update complete!"
Write-Host ""
Write-Host "  Previous : b$currentBuild"
Write-Host "  Installed: b$latestBuild"
if ($verifyOutput) { Write-Host "  Verified : $verifyOutput" }
Write-Host ""

# Cleanup
Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
