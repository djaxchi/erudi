# 🧠 Llama.cpp Integration Guide

This document explains how **Llama.cpp** is integrated into Erudi — how it works, why it exists, and how to build it locally.  
It is the inference engine on **Windows** and **Linux**, in both a **CPU** and a **CUDA** build. macOS uses **MLX** (Apple Silicon only); Intel Mac is not a shipped target. The per-platform build scripts live in `scripts/dev/backend/build-llamacpp-*` (see the README).

---

## 📘 Overview

Erudi embeds a fork of **Llama.cpp** in:

`backend/forks/llama-cpp/`

Llama.cpp provides low-level LLM inference support for CPU and GPU backends.  
Erudi uses it for inference on Windows and Linux — a **CPU** build (universal) and a **CUDA** build (GPU acceleration, with CPU fallback for models larger than VRAM).

Goals:
- Keep Erudi **self-contained** (no Torch, no Transformers)
- Support **cross-platform local inference**
- Provide a unified **CPU Engine** for Windows, Linux, and macOS
- Build everything in CI — no binaries are ever committed

---

## ⚙️ Engine selection per platform

- **Apple Silicon (M1/M2/…)** → **MLX**, optimized for Metal and unified memory.
- **Windows / Linux with an NVIDIA GPU** → llama.cpp **CUDA** build (GPU-accelerated; CPU layers stay on for models larger than VRAM).
- **Windows / Linux without a GPU** → llama.cpp **CPU** build.

The CUDA binary also runs CPU-only, so a driverless machine falls back to it (see `BaseLlamaCppEngine._find_llama_server`).

---

## 🧩 Build process

The CPU version is built using:

`scripts/dev/backend/build-llamacpp-cpu-macos.sh`

This script:
1. Checks system dependencies (Xcode tools, curl, tar).
2. Installs `cmake` inside the Python virtual environment (`backend/venv`) — no global installs.
3. Detects and optionally cleans old builds.
4. Configures CMake for **x86_64 CPU-only**:
   - `GGML_ACCELERATE=ON`: enables Apple’s Accelerate framework (native BLAS)
   - `GGML_BLAS=OFF`: disables third-party BLAS
   - `GGML_NATIVE=OFF`: prevents `-mcpu=native` for cross-compatibility
   - `CMAKE_OSX_ARCHITECTURES="x86_64"`: targets Intel Macs
   - `CMAKE_OSX_DEPLOYMENT_TARGET=10.15`: compatible with macOS Catalina+
5. Builds into:
   `backend/forks/llama-cpp/build-cpu/`
6. Installs artifacts to:
   `backend/artifacts/llama-cpp/cpu/`

---

## 💻 Developing on Apple Silicon

If you’re developing from an Apple Silicon Mac:
- The build produces **x86_64 binaries** using Rosetta cross-compilation.
- Test the Intel build locally with:

  `arch -x86_64 backend/artifacts/llama-cpp/cpu/bin/llama-cli -h`

- MLX continues to power the Silicon build; Llama.cpp is just for Intel fallback testing.

---

## 🪟🧊 OS differences

| OS | Backend | Math/Acceleration | Binary format | Notes |
|----|----------|------------------|----------------|-------|
| macOS | Accelerate | System-native BLAS | `.dylib`, Mach-O | MLX on ARM, Llama.cpp on Intel |
| Linux | OpenBLAS | `.so`, ELF | ELF binaries | Built with gcc/clang |
| Windows | OpenBLAS (vcpkg) | `.dll`, `.exe` | PE/COFF | Uses MSVC or MinGW |

Each platform has its own build script and native toolchain configuration.

---

## 🚫 Git ignore rules

Never commit generated binaries or build outputs:

`backend/forks/llama-cpp/build-*/`
`backend/artifacts/llama-cpp/`


Reasoning:
- Build outputs are **environment-specific**
- CI regenerates clean builds for each OS
- Only official CI artifacts are packaged with Erudi

---

## 🤖 Continuous Integration (CI)

In CI:
- Each OS runner rebuilds Llama.cpp for its environment
- Only the **correct artifact** (matching the target Erudi executable) is included in the installer

Example:
- For Erudi macOS Intel builds → only `backend/artifacts/llama-cpp/cpu/` is packaged
- CI enforces reproducibility and proper architecture targeting
- Artifacts are stripped, optimized, and integrated into the final Erudi bundle

---

## 🧠 Key takeaways

- Llama.cpp provides **CPU inference** for non-MLX systems.
- The script builds **x86_64 binaries** even on Apple Silicon (via Rosetta).
- The build script handles dependencies and architecture flags automatically.
- Never commit builds or artifacts — CI handles official rebuilds.
- Only the right Llama.cpp binary for the current target OS is bundled in production.

---

## ✅ Quick usage

1. Make sure you're setup in the project
For Mac/Linux
```bash
bash ./scripts/dev/backend/setup-*.sh
```

For Windows

```bash
.\scripts\dev\backend\setup-win-cpu.ps1
```

2. Run build script

```
bash scripts/dev/backend/build-llamacpp-cpu-<os>.sh
```

...

3. (Optional) Test build

Important ! If you're developing from a Mac Silicon the version for Mac Intel, run through Rosetta !
```bash
arch -x86_64 backend/artifacts/llama-cpp/cpu/bin/llama-cli -h
```

---

## 📦 Future improvements

- Add optional ROCm (AMD) or Vulkan builds.
- Support universal binaries (`arm64+x86_64`) on macOS.
- Provide a unified `build_all_llamacpp.sh` that builds all OS targets.

---

**TL;DR**  
Run the per-platform build script for your OS — `scripts/dev/backend/build-llamacpp-{cpu,cuda}-{linux,win}` (or `-cpu-macos-silicon` for a local mac CPU build); see the README.  
Don’t commit builds — CI rebuilds the proper artifacts and bundles them with the correct Erudi release. The detailed walkthrough below is illustrative of the approach.