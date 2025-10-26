#!/usr/bin/env bash
# build-llamacpp-cpu-macos.sh
# macOS (Intel/ARM), no Homebrew required.
# Uses CMake from the local Python virtual environment (backend/venv/bin/pip).
# Builds CPU-only version with Accelerate backend, targeting x86_64 (Intel Macs).
# Usage:
#   bash scripts/dev/backend/build-llamacpp-cpu-macos.sh

set -euo pipefail

# ---------------- Config ----------------
SRC_DIR="backend/forks/llama-cpp"
BUILD_DIR="${SRC_DIR}/build-cpu"
INSTALL_DIR="backend/artifacts/llama-cpp/cpu"
VENV_PIP="backend/venv/bin/pip"
VENV_PYTHON="backend/venv/bin/python"
VENV_CMAKE="backend/venv/bin/cmake"
CACHE_DIR="${CACHE_DIR:-/Users/Shared/erudi-cache}"

# ---------------- Helpers ----------------
need() { command -v "$1" >/dev/null 2>&1; }
die()  { echo "ERROR: $*" >&2; exit 1; }

need clang || die "Xcode Command Line Tools are required. Run: xcode-select --install"
need curl  || die "curl is required."
need tar   || die "tar is required."
[ -x "$VENV_PIP" ] || die "Python venv not initialized. Run: python3 -m venv backend/venv && source backend/venv/bin/activate && pip install -U pip"

# ---------------- Clean option ----------------
echo "[clean] Checking for previous build..."
if [ -d "$BUILD_DIR" ] || [ -d "$INSTALL_DIR" ]; then
  echo "The following directories already exist:"
  [ -d "$BUILD_DIR" ] && echo "  - $BUILD_DIR"
  [ -d "$INSTALL_DIR" ] && echo "  - $INSTALL_DIR"
  read -rp "Do you want to delete them before rebuilding? (y/N) " confirm
  if [[ "$confirm" =~ ^[Yy]$ ]]; then
    echo "Removing old build directories..."
    rm -rf "$BUILD_DIR" "$INSTALL_DIR"
    echo "✅ Old build directories removed."
  else
    echo "⏩ Keeping existing directories."
  fi
else
  echo "No previous build detected."
fi

mkdir -p "$CACHE_DIR" "$BUILD_DIR" "$INSTALL_DIR"

# ---------------- CMake via venv ----------------
if [ ! -x "$VENV_CMAKE" ]; then
  echo "[cmake] Installing via $VENV_PIP"
  "$VENV_PIP" install --upgrade cmake >/dev/null
fi

if [ ! -x "$VENV_CMAKE" ]; then
  die "CMake not found in venv after installation. Check backend/venv/bin/"
fi

echo "[cmake] OK → $("$VENV_CMAKE" --version | head -n1)"

# ---------------- Build llama.cpp CPU-only ----------------
echo "[build] CPU-only x86_64 build..."
CMAKE_PREFIX="/System/Library/Frameworks/Accelerate.framework/Versions/A"

"$VENV_CMAKE" -S "$SRC_DIR" -B "$BUILD_DIR" \
  -DGGML_ACCELERATE=ON \
  -DGGML_BLAS=OFF \
  -DGGML_NATIVE=OFF \
  -DCMAKE_OSX_ARCHITECTURES="x86_64" \
  -DCMAKE_OSX_DEPLOYMENT_TARGET=10.15 \
  -DCMAKE_INSTALL_RPATH="@executable_path/../lib" \
  -DGGML_CUDA=OFF -DGGML_HIP=OFF -DGGML_METAL=OFF -DGGML_VULKAN=OFF -DGGML_SYCL=OFF \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_PREFIX_PATH="$CMAKE_PREFIX"

"$VENV_CMAKE" --build "$BUILD_DIR" -j
"$VENV_CMAKE" --install "$BUILD_DIR" --prefix "$INSTALL_DIR"

echo "✅ Done. Binaries → ${INSTALL_DIR}/bin"
