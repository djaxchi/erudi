# build-llamacpp-cpu-win.ps1
#
# Goal:
# - Build llama.cpp for Windows, CPU-only backend (no CUDA).
# - Produces the llama-server.exe used by CPU_Engine on Windows machines without
#   an NVIDIA GPU. (The CUDA build also runs CPU inference, so this is the
#   universal/fallback binary; see BaseLlamaCppEngine._find_llama_server.)
#
# Prerequisites:
# - Visual Studio 2022 with the "Desktop development with C++" workload.
#   GitHub `windows-latest` runners ship this, so no vcvarsall bootstrap is
#   needed: the "Visual Studio 17 2022" CMake generator finds MSVC on its own.
# - Python + cmake. Taken from the dev venv (backend\venv\Scripts) if present,
#   else from PATH (CI installs cmake via pip into the system Python).
# - The llama-cpp submodule populated: git submodule update --init --recursive.
#
# Usage (run from erudi\ or erudi\backend\):
#   .\scripts\dev\backend\build-llamacpp-cpu-win.ps1
#
# Output:
#   backend\artifacts\llama-cpp\cpu\bin\llama-server.exe
#   backend\artifacts\llama-cpp\cpu\bin\llama-quantize.exe
#   backend\artifacts\llama-cpp\cpu\bin\convert_hf_to_gguf.py

$ErrorActionPreference = "Stop"

# -------- helpers --------
function Write-Step  { Write-Host "[build]   $args" -ForegroundColor Cyan }
function Write-OK    { Write-Host "[ok]      $args" -ForegroundColor Green }
function Write-Warn  { Write-Host "[warning] $args" -ForegroundColor Yellow }
function Write-Fail  { Write-Host "[error]   $args" -ForegroundColor Red; exit 1 }

# -------- path resolution (run from erudi\ or erudi\backend\) --------
$currentDir = (Get-Item .).Name
if ($currentDir -eq "backend") {
    $BackendRoot = "."
} elseif (Test-Path "backend") {
    $BackendRoot = "backend"
} else {
    Write-Fail "Run this script from the erudi\ or erudi\backend\ directory."
}

$SrcDir     = Join-Path $BackendRoot "forks\llama-cpp"
$BuildDir   = Join-Path $SrcDir      "build-cpu"
$InstallDir = Join-Path $BackendRoot "artifacts\llama-cpp\cpu"
$BinDir     = Join-Path $InstallDir  "bin"

# Toolchain: prefer the dev venv, fall back to PATH (CI installs into system Python).
$VenvPip   = Join-Path $BackendRoot "venv\Scripts\pip.exe"
$VenvCmake = Join-Path $BackendRoot "venv\Scripts\cmake.exe"
if (-not (Test-Path $VenvPip))   { $VenvPip   = (Get-Command pip   -ErrorAction SilentlyContinue).Source }
if (-not (Test-Path $VenvCmake)) { $VenvCmake = (Get-Command cmake -ErrorAction SilentlyContinue).Source }

Write-Step "Paths resolved:"
Write-Host "  Source  : $SrcDir"
Write-Host "  Build   : $BuildDir"
Write-Host "  Install : $InstallDir"

# -------- sanity checks --------
Write-Step "Checking prerequisites..."

if (-not (Test-Path (Join-Path $SrcDir "CMakeLists.txt"))) {
    Write-Fail "llama-cpp source not found at $SrcDir. Run: git submodule update --init --recursive"
}

# cmake (install into the env if missing)
if (-not $VenvCmake) {
    Write-Step "cmake not found. Installing via pip..."
    if (-not $VenvPip) { Write-Fail "Neither cmake nor pip found on PATH." }
    & $VenvPip install --upgrade cmake --quiet
    if ($LASTEXITCODE -ne 0) { Write-Fail "Failed to install cmake." }
    $VenvCmake = (Get-Command cmake -ErrorAction SilentlyContinue).Source
}
if (-not $VenvCmake) { Write-Fail "cmake still not found after pip install." }
Write-OK "cmake: $((& $VenvCmake --version 2>&1 | Select-Object -First 1))"

# -------- clean previous output (non-interactive: CI runners start fresh) --------
if ((Test-Path $BuildDir) -or (Test-Path $InstallDir)) {
    Write-Step "Removing previous build output..."
    if (Test-Path $BuildDir)   { Remove-Item -Path $BuildDir   -Recurse -Force }
    if (Test-Path $InstallDir) { Remove-Item -Path $InstallDir -Recurse -Force }
    Write-OK "Cleaned."
}
New-Item -ItemType Directory -Force -Path $BuildDir   | Out-Null
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

# -------- cmake configure (CPU-only) --------
# The Visual Studio generator finds and configures MSVC itself, so (unlike the
# CUDA build) we do NOT need the Ninja + vcvarsall bootstrap.
Write-Host ""
Write-Step "Configuring llama.cpp (CPU-only backend)..."

$CmakeArgs = @(
    "-G", "Visual Studio 17 2022",
    "-A", "x64",
    "-S", $SrcDir,
    "-B", $BuildDir,
    "-DCMAKE_BUILD_TYPE=Release",
    "-DBUILD_SHARED_LIBS=OFF",          # static: a single self-contained exe
    "-DCMAKE_INSTALL_PREFIX=$InstallDir",
    "-DLLAMA_CURL=OFF",                 # no libcurl dependency for server-only use
    # ---- backend flags: CPU only ----
    "-DGGML_CUDA=OFF",
    "-DGGML_CPU=ON",
    "-DGGML_NATIVE=OFF",                # portable: no host-specific ISA baked in (clients vary)
    "-DGGML_METAL=OFF",
    "-DGGML_VULKAN=OFF",
    "-DGGML_HIP=OFF",
    "-DGGML_SYCL=OFF",
    "-DGGML_RPC=OFF",
    "-DGGML_WEBGPU=OFF",
    "-DGGML_OPENMP=OFF",
    "-DGGML_BLAS=OFF"
)

Write-Host "  cmake $($CmakeArgs -join ' ')"
Write-Host ""

& $VenvCmake @CmakeArgs
if ($LASTEXITCODE -ne 0) { Write-Fail "cmake configuration failed. Check output above." }

# -------- cmake build --------
Write-Host ""
Write-Step "Compiling (CPU, this takes a few minutes)..."

$CpuCount = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
& $VenvCmake --build $BuildDir --config Release --parallel $CpuCount
if ($LASTEXITCODE -ne 0) { Write-Fail "Build failed. Check output above." }

# -------- cmake install --------
Write-Host ""
Write-Step "Installing to $InstallDir..."

& $VenvCmake --install $BuildDir --config Release
if ($LASTEXITCODE -ne 0) { Write-Fail "Install step failed." }

# -------- copy Python conversion tools (parity with the CUDA build) --------
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

$ConvertScripts = Get-ChildItem -Path $SrcDir -Filter "convert*.py" -ErrorAction SilentlyContinue
if ($ConvertScripts) {
    foreach ($script in $ConvertScripts) {
        Copy-Item -Path $script.FullName -Destination $BinDir -Force
        Write-OK "Copied $($script.Name)"
    }
}

# -------- verify output --------
Write-Host ""
Write-Step "Verifying output..."

$ServerExe   = Join-Path $BinDir "llama-server.exe"
$QuantizeExe = Join-Path $BinDir "llama-quantize.exe"

if (Test-Path $ServerExe) {
    Write-OK "llama.cpp CPU build complete: $ServerExe"
    if (-not (Test-Path $QuantizeExe)) { Write-Warn "Missing (non-fatal): $QuantizeExe" }
} else {
    Write-Warn "llama-server.exe not at $ServerExe. Installed binaries:"
    Get-ChildItem -Path $BinDir -Recurse -Filter "*.exe" | ForEach-Object { Write-Host ('  ' + $_.FullName) }
    Write-Fail "Expected llama-server.exe missing after install."
}
