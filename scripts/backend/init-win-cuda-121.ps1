# Simple and efficient Python environment setup script for Erudi on Windows with CUDA 12.1
# Requirements: PowerShell 5.1+, Python 3.9+

# Helper functions for consistent status messages
function Write-Status($msg) { Write-Host "[STATUS] $msg" -ForegroundColor Cyan }
function Write-Error($msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red; exit 1 }

$currentDir = Split-Path -Leaf (Get-Location)
if ($currentDir -eq "backend") {
    Write-Host "You are currently in erudi/backend/"
    $req = ".\requirements\requirements-win-cuda-121.txt"
    $venvPath = ".\venv"
} else {
    Write-Host "You are currently in erudi/"
    $req = ".\backend\requirements\requirements-win-cuda-121.txt"
    $venvPath = ".\backend\venv"
}

# Check Python version (3.9+)
Write-Status "Checking Python version..."

$pythonCandidates = @("python", "python3", "py", "py3")
$pythonCmd = $null
$version = $null

foreach ($cmd in $pythonCandidates) {
    try {
        $version = & $cmd --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $pythonCmd = $cmd
            break
        }
    } catch {}
}

if (-not $pythonCmd) {
    Write-Error "No valid Python executable found in PATH (tried: $($pythonCandidates -join ', '))"
}

if ($version -match '(\d+)\.(\d+)\.(\d+)') {
    $major = [int]$Matches[1]; $minor = [int]$Matches[2]
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 9)) {
        Write-Error "Python 3.9+ required, found: $version"
    } else {
        Write-Status "Using Python: $pythonCmd ($version)"
    }
} else {
    Write-Error "Could not determine Python version from output: $version"
}

# Create and activate virtual environment
Write-Status "Checking virtual environment in $venvPath..."

# Remove existing venv if any
if (Test-Path $venvPath) {
    $venvConfirmation = Read-Host "A virtual env already exists in $venvPath. Do you want to delete it ? (Y/n)"
    if ($venvConfirmation -eq '' -or $venvConfirmation.ToLower() -eq 'y') {
        Write-Status "Suppression de l'environnement virtuel existant..."
        Remove-Item -Recurse -Force $venvPath
        Write-Status "Creating venv..."
        & python -m venv $venvPath
        if (-not $?) { Write-Error "Failed to create virtual environment" }
    } else {
        Write-Status "L'environnement virtuel existe déjà, les requirements seront installées dedans."
    }
}

# Activate venv
Write-Status "Activating virtual environment..."
& "$venvPath\Scripts\Activate.ps1"
if (-not $?) { Write-Error "Failed to activate virtual environment" }

$venvPython = Join-Path $venvPath "Scripts\python.exe"

# Upgrade pip
Write-Status "Upgrading pip..."
& $venvPython -m pip install --upgrade pip
if (-not $?) { Write-Error "Failed to upgrade pip" }

# Install requirements
$forceReinstallConfirmation = Read-Host "Do you want to --force-reinstall the requirements ? (Y/n)"
if ($forceReinstallConfirmation -eq '' -or $forceReinstallConfirmation.ToLower() -eq 'y') {
    Write-Status "Installing requirements from $req..."
    & $venvPython -m pip install --no-cache-dir --force-reinstall -r $req
    if (-not $?) { Write-Error "Failed to install requirements from $req" }
} else {
    Write-Status "Installing requirements from $req..."
    & $venvPython -m pip install --no-cache-dir -r $req
    if (-not $?) { Write-Error "Failed to install requirements from $req" }
}

Write-Host ""
Write-Host "Environment setup complete! Welcome on-board at Erudi! " -ForegroundColor Green
Write-Host "You can now run: 'uvicorn src.main:app' inside backend/ and after sourcing the venv."
Write-Host ""