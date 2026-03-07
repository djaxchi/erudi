# build-llamacpp-cuda-win.ps1
#
# Goal:
# - Build llama.cpp for Windows with NVIDIA CUDA 12.1 GPU backend.
# - Enables GPU-accelerated inference via CUDA_Engine.
# - CPU fallback layers remain active for models larger than VRAM.
#
# Prerequisites (must be installed before running this script):
# - Visual Studio 2019 or 2022 with "Desktop development with C++" workload
# - NVIDIA CUDA Toolkit 12.1 (sets CUDA_PATH env var automatically)
# - Python 3.9+ and the Erudi venv already created via setup-win-cuda-121.ps1
# - Git (for the llama-cpp submodule, if not already populated)
#
# Usage (run from erudi\ or erudi\backend\):
#   .\scripts\dev\backend\build-llamacpp-cuda-win.ps1
#
# Output:
#   backend\artifacts\llama-cpp\cuda\bin\llama-server.exe
#   backend\artifacts\llama-cpp\cuda\bin\llama-quantize.exe
#   backend\artifacts\llama-cpp\cuda\bin\convert_hf_to_gguf.py

$ErrorActionPreference = "Stop"

# -------- helpers --------
function Write-Step  { Write-Host "[build]   $args" -ForegroundColor Cyan }
function Write-OK    { Write-Host "[ok]      $args" -ForegroundColor Green }
function Write-Warn  { Write-Host "[warning] $args" -ForegroundColor Yellow }
function Write-Fail  { Write-Host "[error]   $args" -ForegroundColor Red; exit 1 }

# -------- path resolution --------
# Support running from either erudi\ or erudi\backend\
$currentDir = (Get-Item .).Name
if ($currentDir -eq "backend") {
    $BackendRoot = "."
} elseif (Test-Path "backend") {
    $BackendRoot = "backend"
} else {
    Write-Fail "Run this script from the erudi\ or erudi\backend\ directory."
}

$SrcDir     = Join-Path $BackendRoot "forks\llama-cpp"
$BuildDir   = Join-Path $SrcDir      "build-cuda"
$InstallDir = Join-Path $BackendRoot "artifacts\llama-cpp\cuda"
$BinDir     = Join-Path $InstallDir  "bin"
$VenvPip    = Join-Path $BackendRoot "venv\Scripts\pip.exe"
$VenvPython = Join-Path $BackendRoot "venv\Scripts\python.exe"
$VenvCmake  = Join-Path $BackendRoot "venv\Scripts\cmake.exe"

Write-Step "Paths resolved:"
Write-Host "  Source  : $SrcDir"
Write-Host "  Build   : $BuildDir"
Write-Host "  Install : $InstallDir"

# -------- sanity checks --------
Write-Step "Checking prerequisites..."

# llama-cpp submodule present
if (-not (Test-Path (Join-Path $SrcDir "CMakeLists.txt"))) {
    Write-Fail "llama-cpp source not found at $SrcDir. Run: git submodule update --init --recursive"
}

# Python venv
if (-not (Test-Path $VenvPython)) {
    Write-Fail "Python venv not found at $BackendRoot\venv. Run setup-win-cuda-121.ps1 first."
}

# -------- CUDA toolkit detection --------
Write-Step "Detecting CUDA 12.1 toolkit..."

# Prefer version-specific env var set by the CUDA installer
$CudaPath = $null
foreach ($candidate in @($env:CUDA_PATH_V12_1, $env:CUDA_PATH, "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.1")) {
    if ($candidate -and (Test-Path (Join-Path $candidate "bin\nvcc.exe"))) {
        $CudaPath = $candidate
        break
    }
}

if (-not $CudaPath) {
    Write-Fail (
        "CUDA 12.1 toolkit not found.`n" +
        "Install CUDA 12.1 from https://developer.nvidia.com/cuda-12-1-0-download-archive`n" +
        "Expected nvcc.exe at: C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.1\bin\nvcc.exe`n" +
        "Or set the CUDA_PATH_V12_1 environment variable manually."
    )
}

$Nvcc = Join-Path $CudaPath "bin\nvcc.exe"
$NvccVersion = (& $Nvcc --version 2>&1 | Select-String "release") -replace ".*release ([0-9.]+).*", 'CUDA $1'
Write-OK "CUDA toolkit : $CudaPath"
Write-OK "nvcc         : $NvccVersion"

# -------- Visual Studio detection + MSVC environment bootstrap --------
# We use -G Ninja instead of the Visual Studio generator because the VS generator
# requires the CUDA VS toolset integration (.props files) which is only present when
# the full VS IDE is installed. Ninja + vcvarsall works with Build Tools too.

Write-Step "Detecting Visual Studio (C++ build tools) and bootstrapping MSVC environment..."

$VsWhere = "C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
$VcVarsAll = $null

if (Test-Path $VsWhere) {
    $VsInstallPath = & $VsWhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2>&1
    if ($VsInstallPath) {
        $candidate = Join-Path $VsInstallPath "VC\Auxiliary\Build\vcvarsall.bat"
        if (Test-Path $candidate) { $VcVarsAll = $candidate }
    }
}

if (-not $VcVarsAll) {
    Write-Fail (
        "vcvarsall.bat not found. Install Visual Studio 2019/2022 with the `n" +
        "'Desktop development with C++' workload, or open a VS Developer prompt and re-run."
    )
}

Write-OK "Found vcvarsall.bat: $VcVarsAll"
Write-Step "Bootstrapping MSVC x64 environment into current session..."

# Capture env vars set by vcvarsall.bat and apply them to this PowerShell session
$tmpEnvFile = [System.IO.Path]::GetTempFileName()
try {
    cmd /c "`"$VcVarsAll`" x64 > nul 2>&1 && set" | Set-Content $tmpEnvFile
    Get-Content $tmpEnvFile | ForEach-Object {
        if ($_ -match '^([^=]+)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
        }
    }
} finally {
    Remove-Item $tmpEnvFile -Force -ErrorAction SilentlyContinue
}

# Verify cl.exe is now in PATH
$ClExe = Get-Command cl.exe -ErrorAction SilentlyContinue
if (-not $ClExe) {
    Write-Fail "cl.exe not found in PATH after vcvarsall bootstrap. Check VS installation."
}
Write-OK "MSVC cl.exe: $($ClExe.Source)"

# Verify ninja is available (ships with VS Build Tools)
$NinjaExe = Get-Command ninja -ErrorAction SilentlyContinue
if (-not $NinjaExe) {
    Write-Fail (
        "ninja not found in PATH after vcvarsall bootstrap.`n" +
        "Ensure 'C++ CMake tools for Windows' is installed in VS Build Tools."
    )
}
Write-OK "Ninja: $($NinjaExe.Source)"

# -------- cmake detection / install --------
Write-Step "Checking cmake..."

if (-not (Test-Path $VenvCmake)) {
    Write-Step "cmake not found in venv. Installing via pip..."
    & $VenvPip install --upgrade cmake --quiet
    if ($LASTEXITCODE -ne 0) { Write-Fail "Failed to install cmake into venv." }
}

if (-not (Test-Path $VenvCmake)) { Write-Fail "cmake still not found at $VenvCmake after pip install." }

$CmakeVersion = (& $VenvCmake --version 2>&1 | Select-Object -First 1)
Write-OK "cmake: $CmakeVersion"

# -------- optional clean --------
$doClean = $false
if ((Test-Path $BuildDir) -or (Test-Path $InstallDir)) {
    Write-Host ""
    Write-Host "Existing build output found:"
    if (Test-Path $BuildDir)   { Write-Host "  - $BuildDir" }
    if (Test-Path $InstallDir) { Write-Host "  - $InstallDir" }
    $confirm = Read-Host "Delete before rebuild? [Y/n]"
    if ([string]::IsNullOrEmpty($confirm)) { $confirm = "Y" }
    if ($confirm -match "^[Yy]") { $doClean = $true }
} else {
    Write-Step "No previous build found."
}

if ($doClean) {
    Write-Step "Removing old build output..."
    if (Test-Path $BuildDir)   { Remove-Item -Path $BuildDir   -Recurse -Force }
    if (Test-Path $InstallDir) { Remove-Item -Path $InstallDir -Recurse -Force }
    Write-OK "Cleaned."
}

New-Item -ItemType Directory -Force -Path $BuildDir   | Out-Null
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

# -------- cmake configure --------
Write-Host ""
Write-Step "Configuring llama.cpp with CUDA 12.1..."

$CmakeArgs = @(
    "-G", "Ninja",                       # Ninja avoids CUDA VS toolset registration requirement
    "-S", $SrcDir,
    "-B", $BuildDir,
    "-DCMAKE_BUILD_TYPE=Release",
    "-DBUILD_SHARED_LIBS=OFF",          # Static linkage avoids DLL placement issues on Windows
    "-DCMAKE_INSTALL_PREFIX=$InstallDir",
    "-DCMAKE_CUDA_COMPILER=$Nvcc",
    "-DCMAKE_CUDA_FLAGS=-allow-unsupported-compiler -Xcompiler /D_ALLOW_COMPILER_AND_STL_VERSION_MISMATCH -gencode=arch=compute_89,code=compute_89",
    "-DCMAKE_CXX_FLAGS=/D_ALLOW_COMPILER_AND_STL_VERSION_MISMATCH",   # MSVC STL 19.44 requires CUDA 12.4+; bypass its static_assert
    "-DLLAMA_CURL=OFF",                 # No libcurl dependency needed for server-only use
    # ---- backend flags ----
    "-DGGML_CUDA=ON",                   # Enable NVIDIA CUDA backend
    "-DCMAKE_CUDA_ARCHITECTURES=50;61;70;75;80;86;89",  # Native SASS for SM 50-89 + PTX 89 forward compat (Blackwell JIT-compiles from PTX)
    "-DGGML_CPU=ON",                    # Keep CPU layers for overflow beyond VRAM
    "-DGGML_NATIVE=OFF",                # OFF for portable binary across same-gen GPUs
    "-DGGML_CUDA_F16=ON",               # Enable FP16 operations for faster inference
    "-DGGML_METAL=OFF",
    "-DGGML_VULKAN=OFF",
    "-DGGML_HIP=OFF",
    "-DGGML_SYCL=OFF",
    "-DGGML_RPC=OFF",
    "-DGGML_WEBGPU=OFF",
    "-DGGML_OPENMP=OFF",
    "-DGGML_ACCELERATE=OFF",
    "-DGGML_BLAS=OFF"
)

Write-Host "  cmake $($CmakeArgs -join ' ')"
Write-Host ""

& $VenvCmake @CmakeArgs
if ($LASTEXITCODE -ne 0) { Write-Fail "cmake configuration failed. Check output above." }

# -------- cmake build --------
Write-Host ""
Write-Step "Compiling (this takes 5-15 minutes)..."

$CpuCount = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
& $VenvCmake --build $BuildDir --config Release --parallel $CpuCount
if ($LASTEXITCODE -ne 0) { Write-Fail "Build failed. Check output above." }

# -------- cmake install --------
Write-Host ""
Write-Step "Installing to $InstallDir..."

& $VenvCmake --install $BuildDir --config Release
if ($LASTEXITCODE -ne 0) { Write-Fail "Install step failed." }

# -------- copy Python conversion tools --------
Write-Step "Copying Python conversion tools..."

$GgufPySrc  = Join-Path $SrcDir "gguf-py"
$GgufPyDest = Join-Path $BinDir "gguf-py"

if (Test-Path $GgufPySrc) {
    if (Test-Path $GgufPyDest) { Remove-Item $GgufPyDest -Recurse -Force }
    Copy-Item -Path $GgufPySrc -Destination $GgufPyDest -Recurse
    Write-OK "gguf-py module copied to $GgufPyDest"
} else {
    Write-Warn "gguf-py not found at $GgufPySrc - HF to GGUF conversion will not work."
}

# Copy convert_hf_to_gguf.py and any other convert*.py scripts
$ConvertScripts = Get-ChildItem -Path $SrcDir -Filter "convert*.py" -ErrorAction SilentlyContinue
if ($ConvertScripts) {
    foreach ($script in $ConvertScripts) {
        Copy-Item -Path $script.FullName -Destination $BinDir -Force
        Write-OK "Copied $($script.Name)"
    }
} else {
    Write-Warn "No convert*.py scripts found in $SrcDir"
}

# -------- verify output --------
Write-Host ""
Write-Step "Verifying output..."

$ServerExe   = Join-Path $BinDir "llama-server.exe"
$QuantizeExe = Join-Path $BinDir "llama-quantize.exe"

$allOk = $true
foreach ($bin in @($ServerExe, $QuantizeExe)) {
    if (Test-Path $bin) {
        Write-OK "Found: $bin"
    } else {
        Write-Warn "Missing: $bin"
        $allOk = $false
    }
}

Write-Host ""
if ($allOk) {
    Write-OK "llama.cpp CUDA build complete."
    Write-Host ""
    Write-Host "Artifacts installed to: $InstallDir"
    Write-Host ""
    Write-Host "Test with:"
    Write-Host "  $ServerExe --version"
    Write-Host "  $QuantizeExe --help"
} else {
    Write-Warn "Build completed but some expected binaries are missing."
    Write-Warn "Check $BinDir for what was installed."
    Write-Warn "The server binary may be under a sub-path like $BinDir\Release\ if cmake used the Release config subfolder."
    Write-Host ""
    Write-Host "All installed files:"
    Get-ChildItem -Path $BinDir -Recurse -Filter "*.exe" | ForEach-Object { Write-Host ('  ' + $_.FullName) }
}
