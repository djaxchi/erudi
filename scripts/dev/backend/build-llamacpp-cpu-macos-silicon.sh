#!/usr/bin/env bash
# build-llamacpp-cpu-macos-silicon.sh
#
# Goal:
# - Build llama.cpp for Apple Silicon host (arm64).
# - Target = Apple Silicon CPU backend only.
# - No CUDA, no Vulkan, no HIP, etc.
# - We keep Accelerate ON for fast matmul.
# - We keep Metal OFF because CPU_Engine will call llama.cpp as pure CPU.
#
# This script:
# - Creates a clean build dir and install dir.
# - Uses cmake from backend/venv so we do not depend on Homebrew.
# - Installs into backend/artifacts/llama-cpp/cpu.
#
# Usage:
#   bash scripts/dev/backend/build-llamacpp-cpu-macos-silicon.sh

set -euo pipefail

# -------- config --------
SRC_DIR="backend/forks/llama-cpp"
BUILD_DIR="${SRC_DIR}/build-cpu"
INSTALL_DIR="backend/artifacts/llama-cpp/cpu"

VENV_PIP="backend/venv/bin/pip"
VENV_CMAKE="backend/venv/bin/cmake"

# -------- helpers --------
need() { command -v "$1" >/dev/null 2>&1; }
die()  { echo "ERROR: $*" >&2; exit 1; }

# basic sanity
need clang    || die "Xcode Command Line Tools required. Run: xcode-select --install"
need curl     || die "curl required"
need tar      || die "tar required"
[ -x "$VENV_PIP" ] || die "Python venv missing. Run: python3 -m venv backend/venv && backend/venv/bin/pip install --upgrade pip"

# -------- optional clean --------
echo "[clean] Checking for previous build..."
if [ -d "$BUILD_DIR" ] || [ -d "$INSTALL_DIR" ]; then
  echo "Existing:"
  [ -d "$BUILD_DIR" ] && echo "  - $BUILD_DIR"
  [ -d "$INSTALL_DIR" ] && echo "  - $INSTALL_DIR"
  read -rp "Delete before rebuild? (y/N) " confirm
  if [[ "$confirm" =~ ^[Yy]$ ]]; then
    rm -rf "$BUILD_DIR" "$INSTALL_DIR"
    echo "[clean] Removed old build output"
  else
    echo "[clean] Keeping old output"
  fi
else
  echo "[clean] No previous build"
fi

mkdir -p "$BUILD_DIR" "$INSTALL_DIR"

# -------- cmake in venv --------
if [ ! -x "$VENV_CMAKE" ]; then
  echo "[cmake] Installing cmake into venv"
  "$VENV_PIP" install --upgrade cmake >/dev/null
fi

[ -x "$VENV_CMAKE" ] || die "cmake not found in backend/venv/bin after install"

echo "[cmake] $( "$VENV_CMAKE" --version | head -n1 )"

# -------- configure --------
echo "[build] Configuring for Apple Silicon CPU backend (arm64)..."

# Notes:
# - We do NOT set CMAKE_OSX_ARCHITECTURES explicitly. We let it default to arm64.
#   That prevents cross-arch weirdness and avoids long feature detection workarounds.
# - GGML_NATIVE=ON lets ggml pick Apple M* optimized kernels (apple_m1 / m2_m3 / m4 etc).
#   This will emit multiple CPU backend variants under the hood.
# - GGML_METAL=OFF so we do not pull Metal kernels. CPU_Engine will not call Metal.
# - GGML_OPENMP=OFF to skip OpenMP detection and avoid long hangs in feature probes.
#   AppleClang does not ship libomp by default. This avoids that probe and link noise.
# - We keep GGML_ACCELERATE=ON to link Accelerate for BLAS.
#
# -DCMAKE_INSTALL_RPATH sets @executable_path/../lib so llama-cli finds libllama.dylib at runtime.
#   This keeps runtime self contained inside backend/artifacts/llama-cpp/cpu.

"$VENV_CMAKE" -S "$SRC_DIR" -B "$BUILD_DIR" \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_SHARED_LIBS=ON \
  -DCMAKE_INSTALL_PREFIX="$INSTALL_DIR" \
  -DCMAKE_INSTALL_RPATH="@executable_path/../lib" \
  \
  -DGGML_CPU=ON \
  -DGGML_NATIVE=ON \
  -DGGML_CPU_ALL_VARIANTS=OFF \
  -DGGML_ACCELERATE=ON \
  -DGGML_BLAS=OFF \
  -DGGML_OPENMP=OFF \
  -DGGML_METAL=OFF \
  -DGGML_CUDA=OFF \
  -DGGML_HIP=OFF \
  -DGGML_VULKAN=OFF \
  -DGGML_SYCL=OFF \
  -DGGML_RPC=OFF \
  -DGGML_WEBGPU=OFF

# -------- build --------
echo "[build] Compiling..."
"$VENV_CMAKE" --build "$BUILD_DIR" --config Release -j

# -------- install --------
echo "[install] Installing to $INSTALL_DIR..."
"$VENV_CMAKE" --install "$BUILD_DIR" --config Release

# -------- install Python conversion tools --------
PYTHON_TOOLS_SRC="${SRC_DIR}/gguf-py"
PYTHON_TOOLS_DEST="${INSTALL_DIR}/bin/gguf-py"

if [ -d "$PYTHON_TOOLS_SRC" ]; then
  echo "[install] Copying Python gguf-py module..."
  cp -r "$PYTHON_TOOLS_SRC" "$PYTHON_TOOLS_DEST"
  echo "[install] Python tools available at: $PYTHON_TOOLS_DEST"
else
  echo "[warning] gguf-py not found at $PYTHON_TOOLS_SRC"
  echo "[warning] HF→GGUF conversion will not work without it"
fi

# Copy conversion scripts
echo "[install] Copying conversion scripts..."
cp "${SRC_DIR}"/convert*.py "${INSTALL_DIR}/bin/" 2>/dev/null || true

echo "[done] llama.cpp CPU artifacts available under: $INSTALL_DIR"
echo "[done] test with:"
echo "       backend/artifacts/llama-cpp/cpu/bin/llama-cli -h"
echo "       backend/artifacts/llama-cpp/cpu/bin/convert_hf_to_gguf.py --help"
