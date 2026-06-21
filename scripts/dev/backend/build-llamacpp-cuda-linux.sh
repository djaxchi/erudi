#!/usr/bin/env bash
# build-llamacpp-cuda-linux.sh
#
# Goal:
# - Build llama.cpp for Linux with the NVIDIA CUDA backend.
# - Produces the GPU-accelerated llama-server used by CUDA_Engine on Linux.
#   CPU layers stay ON for models larger than VRAM.
#
# Output: backend/artifacts/llama-cpp/cuda/bin/llama-server
#
# Prerequisites:
# - The CUDA toolkit (nvcc) — on PATH, or under $CUDA_HOME / $CUDA_PATH, or the
#   default /usr/local/cuda. Compilation needs the toolkit but NOT a GPU (only
#   runtime does). CI installs it via Jimver/cuda-toolkit.
# - A C/C++ compiler + cmake (venv or PATH; pip-installed on CI).
#
# Usage (from erudi/ or erudi/backend/):
#   bash scripts/dev/backend/build-llamacpp-cuda-linux.sh

set -euo pipefail

# -------- path resolution --------
if [ -d "backend/forks/llama-cpp" ]; then
  BACKEND_ROOT="backend"
elif [ -d "forks/llama-cpp" ]; then
  BACKEND_ROOT="."
else
  echo "ERROR: run from the erudi/ or erudi/backend/ directory" >&2
  exit 1
fi

SRC_DIR="${BACKEND_ROOT}/forks/llama-cpp"
BUILD_DIR="${SRC_DIR}/build-cuda"
INSTALL_DIR="${BACKEND_ROOT}/artifacts/llama-cpp/cuda"
BIN_DIR="${INSTALL_DIR}/bin"

need() { command -v "$1" >/dev/null 2>&1; }
die()  { echo "ERROR: $*" >&2; exit 1; }

[ -f "${SRC_DIR}/CMakeLists.txt" ] || die "llama-cpp source missing at ${SRC_DIR}. Run: git submodule update --init --recursive"
need cc || need gcc || die "a C compiler (gcc) is required"

# -------- locate nvcc --------
NVCC=""
if need nvcc; then
  NVCC="$(command -v nvcc)"
else
  for d in "${CUDA_HOME:-}" "${CUDA_PATH:-}" /usr/local/cuda; do
    [ -n "$d" ] && [ -x "$d/bin/nvcc" ] && { NVCC="$d/bin/nvcc"; export PATH="$d/bin:$PATH"; break; }
  done
fi
[ -n "$NVCC" ] || die "nvcc (CUDA toolkit) not found. Install CUDA or set CUDA_HOME."
echo "[cuda] nvcc: $("$NVCC" --version | grep -i release || echo "$NVCC")"

# -------- toolchain: prefer venv cmake, fall back to PATH --------
CMAKE="${BACKEND_ROOT}/venv/bin/cmake"
if [ ! -x "$CMAKE" ]; then
  if need cmake; then
    CMAKE="$(command -v cmake)"
  else
    "${BACKEND_ROOT}/venv/bin/pip" install --upgrade cmake >/dev/null 2>&1 || pip install --upgrade cmake >/dev/null
    CMAKE="$(command -v cmake)"
  fi
fi
[ -n "$CMAKE" ] || die "cmake not found and could not be installed"
echo "[cmake] $("$CMAKE" --version | head -n1)"

# -------- clean (non-interactive on CI / non-TTY) --------
if [ -d "$BUILD_DIR" ] || [ -d "$INSTALL_DIR" ]; then
  if [ -t 0 ]; then
    read -rp "Existing build output found. Delete before rebuild? (y/N) " confirm
    [[ "$confirm" =~ ^[Yy]$ ]] && rm -rf "$BUILD_DIR" "$INSTALL_DIR"
  else
    rm -rf "$BUILD_DIR" "$INSTALL_DIR"
  fi
fi
mkdir -p "$BUILD_DIR" "$INSTALL_DIR"

# -------- configure (CUDA backend + CPU fallback layers) --------
echo "[build] Configuring llama.cpp (Linux CUDA)..."
"$CMAKE" -S "$SRC_DIR" -B "$BUILD_DIR" \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_SHARED_LIBS=OFF \
  -DCMAKE_INSTALL_PREFIX="$INSTALL_DIR" \
  -DCMAKE_CUDA_COMPILER="$NVCC" \
  -DLLAMA_CURL=OFF \
  -DGGML_CUDA=ON \
  -DCMAKE_CUDA_ARCHITECTURES="50;61;70;75;80;86;89" \
  -DGGML_CPU=ON \
  -DGGML_NATIVE=OFF \
  -DGGML_CUDA_F16=ON \
  -DGGML_METAL=OFF \
  -DGGML_VULKAN=OFF \
  -DGGML_HIP=OFF \
  -DGGML_SYCL=OFF \
  -DGGML_RPC=OFF \
  -DGGML_WEBGPU=OFF \
  -DGGML_OPENMP=OFF \
  -DGGML_BLAS=OFF

# -------- build + install --------
echo "[build] Compiling (this takes a while)..."
"$CMAKE" --build "$BUILD_DIR" --config Release -j"$(nproc 2>/dev/null || echo 4)"
echo "[install] Installing to $INSTALL_DIR..."
"$CMAKE" --install "$BUILD_DIR" --config Release

# -------- Python conversion tools --------
if [ -d "${SRC_DIR}/gguf-py" ]; then
  rm -rf "${BIN_DIR}/gguf-py"
  cp -r "${SRC_DIR}/gguf-py" "${BIN_DIR}/gguf-py"
fi
cp "${SRC_DIR}"/convert*.py "${BIN_DIR}/" 2>/dev/null || true

# -------- verify --------
[ -x "${BIN_DIR}/llama-server" ] || die "llama-server missing after install (check ${BIN_DIR})"
echo "[done] llama.cpp CUDA build complete: ${BIN_DIR}/llama-server"
