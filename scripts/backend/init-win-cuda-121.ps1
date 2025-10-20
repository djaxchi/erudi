# Simple and efficient Python environment setup script for Erudi on Windows with CUDA 12.1
# Requirements: PowerShell 5.1+, Python 3.9+

# Helper functions for consistent status messages
function Write-Status($msg) { Write-Host "[STATUS] $msg" -ForegroundColor Cyan }
function Write-Error($msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red; exit 1 }

# Check Python version (3.9+)
Write-Status "Checking Python version..."
try {
    $version = python --version 2>&1
    if ($version -match '(\d+)\.(\d+)\.(\d+)') {
        $major = [int]$Matches[1]; $minor = [int]$Matches[2]
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 9)) {
            Write-Error "Python 3.9+ required, found: $version"
        }
    } else {
        Write-Error "Could not determine Python version"
    }
} catch {
    Write-Error "Python not found in PATH"
}

# Create and activate virtual environment
$venvPath = ".\backend\venv"
Write-Status "Creating virtual environment in $venvPath..."

# Remove existing venv if any
if (Test-Path $venvPath) {
    Remove-Item -Recurse -Force $venvPath
}

# Create new venv
python -m venv $venvPath
if (-not $?) { Write-Error "Failed to create virtual environment" }

# Activate venv
Write-Status "Activating virtual environment..."
& "$venvPath\Scripts\Activate.ps1"
if (-not $?) { Write-Error "Failed to activate virtual environment" }

# Upgrade pip
Write-Status "Upgrading pip..."
python -m pip install --upgrade pip
if (-not $?) { Write-Error "Failed to upgrade pip" }

# Install requirements
$req = ".\backend\requirements\requirements-win-cuda-121.txt"
Write-Status "Installing requirements from $req..."
python -m pip install -r $req
if (-not $?) { Write-Error "Failed to install requirements from $req" }

Write-Host ""
Write-Host "Environment setup complete! Welcome on-board at Erudi! " -ForegroundColor Green
Write-Host "You can now run: 'uvicorn src.main:app' inside backend/ and after sourcing the venv."
Write-Host ""