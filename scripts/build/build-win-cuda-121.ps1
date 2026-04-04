# build-win-cuda-121.ps1
#
# Full build pipeline for Erudi on Windows with CUDA 12.1.
#
# Steps:
#   1. Verify prerequisites (Python venv, llama-cpp binaries, Node/npm)
#   2. Install PyInstaller into the backend venv (if missing)
#   3. Generate icon.ico from icon.png (if missing)
#   4. Run PyInstaller with backend.spec  → backend/dist/backend/
#   5. Copy backend bundle into frontend/  → frontend/backend/
#   6. Run `npm run dist:win` in frontend/ → electron-forge package + electron-builder NSIS
#
# Usage (from repo root):
#   .\scripts\build\build-win-cuda-121.ps1
#
# Output:
#   frontend\out\installer\Erudi Setup 1.0.0.exe

$ErrorActionPreference = "Stop"

function Write-Step { Write-Host "`n[build]   $args" -ForegroundColor Cyan }
function Write-OK   { Write-Host "[ok]      $args" -ForegroundColor Green }
function Write-Warn { Write-Host "[warning] $args" -ForegroundColor Yellow }
function Write-Fail { Write-Host "[error]   $args" -ForegroundColor Red; exit 1 }

# ── Path resolution ────────────────────────────────────────────────────────────
$RepoRoot = (Get-Item $PSScriptRoot).Parent.Parent.FullName
$BackendRoot  = Join-Path $RepoRoot "backend"
$FrontendRoot = Join-Path $RepoRoot "frontend"
$VenvPython   = Join-Path $BackendRoot "venv\Scripts\python.exe"
$VenvPip      = Join-Path $BackendRoot "venv\Scripts\pip.exe"
$BackendSpec  = Join-Path $BackendRoot "backend.spec"
$BackendDist  = Join-Path $BackendRoot "dist\backend"
$FrontendBackend = Join-Path $FrontendRoot "backend"
$IconPng      = Join-Path $FrontendRoot "assets\icons\icon.png"
$IconIco      = Join-Path $FrontendRoot "assets\icons\icon.ico"
$LlamaServer  = Join-Path $BackendRoot "artifacts\llama-cpp\cuda\bin\llama-server.exe"

Write-Step "Erudi Windows CUDA 12.1 build"
Write-Host "  Repo root : $RepoRoot"
Write-Host "  Backend   : $BackendRoot"
Write-Host "  Frontend  : $FrontendRoot"

# ── Prerequisites ──────────────────────────────────────────────────────────────
Write-Step "Checking prerequisites..."

if (-not (Test-Path $VenvPython)) {
    Write-Fail "Backend venv not found at $VenvPython.`nRun: .\scripts\dev\backend\setup-win-cuda-121.ps1"
}
Write-OK "Backend venv found"

if (-not (Test-Path $LlamaServer)) {
    Write-Fail "llama-server.exe not found at $LlamaServer.`nRun: .\scripts\dev\backend\build-llamacpp-cuda-win.ps1"
}
Write-OK "llama-server.exe found"

if (-not (Test-Path $BackendSpec)) {
    Write-Fail "backend.spec not found at $BackendSpec."
}
Write-OK "backend.spec found"

$npmCmd = Get-Command npm -ErrorAction SilentlyContinue
if (-not $npmCmd) { Write-Fail "npm not found in PATH. Install Node.js 18+." }
Write-OK "npm found: $($npmCmd.Source)"

# ── PyInstaller ────────────────────────────────────────────────────────────────
Write-Step "Checking PyInstaller..."
$pyiVersion = $null
try {
    $pyiVersion = & $VenvPython -m PyInstaller --version 2>$null
} catch { }
if (-not $pyiVersion) {
    Write-Step "PyInstaller not installed. Installing..."
    & $VenvPip install pyinstaller
    if ($LASTEXITCODE -ne 0) { Write-Fail "Failed to install PyInstaller." }
    $pyiVersion = & $VenvPython -m PyInstaller --version 2>$null
}
Write-OK "PyInstaller $pyiVersion"

# ── icon.ico ───────────────────────────────────────────────────────────────────
Write-Step "Checking icon.ico..."
if (-not (Test-Path $IconIco)) {
    if (Test-Path $IconPng) {
        Write-Step "Generating icon.ico from icon.png using Pillow..."
        $iconScript = @"
from PIL import Image
img = Image.open(r'$IconPng').convert('RGBA')
sizes = [(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)]
img.save(r'$IconIco', format='ICO', sizes=sizes)
print('icon.ico created')
"@
        $iconScript | & $VenvPython
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "Could not generate icon.ico (Pillow may not be installed). Build will use default icon."
        } else {
            Write-OK "icon.ico created at $IconIco"
        }
    } else {
        Write-Warn "icon.png not found. Build will use default icon."
    }
} else {
    Write-OK "icon.ico already exists"
}

# ── Build backend with PyInstaller ─────────────────────────────────────────────
Write-Step "Building backend with PyInstaller (this takes 5-15 minutes)..."
Push-Location $BackendRoot
try {
    & $VenvPython -m PyInstaller backend.spec --noconfirm
    if ($LASTEXITCODE -ne 0) { Write-Fail "PyInstaller build failed." }
} finally {
    Pop-Location
}

if (-not (Test-Path (Join-Path $BackendDist "backend.exe"))) {
    Write-Fail "backend.exe not found after PyInstaller build. Check output above."
}
Write-OK "PyInstaller build complete: $BackendDist\backend.exe"

# ── Copy backend bundle into frontend ─────────────────────────────────────────
Write-Step "Copying backend bundle to frontend..."
if (Test-Path $FrontendBackend) {
    Write-Step "Removing old frontend/backend/..."
    Remove-Item -Path $FrontendBackend -Recurse -Force
}
Copy-Item -Path $BackendDist -Destination $FrontendBackend -Recurse
Write-OK "Backend copied to $FrontendBackend"

# ── Install frontend dependencies if needed ────────────────────────────────────
Write-Step "Checking frontend node_modules..."
if (-not (Test-Path (Join-Path $FrontendRoot "node_modules"))) {
    Write-Step "Installing frontend dependencies..."
    Push-Location $FrontendRoot
    try {
        cmd /c "npm install"
        if ($LASTEXITCODE -ne 0) { Write-Fail "npm install failed." }
    } finally {
        Pop-Location
    }
} else {
    Write-OK "node_modules already present"
}

# ── Clean old out/ to prevent stale resources from previous builds ─────────────
$OutDir = Join-Path $FrontendRoot "out"
if (Test-Path $OutDir) {
    Write-Step "Removing stale out/ directory..."
    Remove-Item -Path $OutDir -Recurse -Force
    Write-OK "Cleaned out/"
}

# ── Build Electron app + NSIS installer ───────────────────────────────────────
Write-Step "Building Electron app and NSIS installer (electron-forge package + electron-builder)..."
Push-Location $FrontendRoot
try {
    cmd /c "npm run dist:win"
    if ($LASTEXITCODE -ne 0) { Write-Fail "dist:win failed." }
} finally {
    Pop-Location
}

# ── Report output ──────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-OK "Build complete!"
Write-Host ""
Write-Host "Installer output:"

$installerOut = Join-Path $FrontendRoot "out\installer"
if (Test-Path $installerOut) {
    Get-ChildItem -Path $installerOut -Include "*.exe" | ForEach-Object {
        Write-Host "  $($_.FullName)" -ForegroundColor White
    }
} else {
    Write-Warn "out/installer directory not found. Check build output above."
}
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "To install:" -ForegroundColor Cyan
Write-Host "  Run 'Erudi Setup 1.0.0.exe' - installs to the user's AppData by default."
Write-Host ""
