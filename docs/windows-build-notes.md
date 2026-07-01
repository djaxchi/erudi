# Windows Build Notes

## Current State (2026-04-01)

| Output | Size | Status |
|---|---|---|
| PyInstaller bundle (`frontend/backend/`) | 2.3 GB | ✅ |
| NSIS installer (`out/installer/Erudi Setup <version>.exe`) | ~1.3 GB est. | ✅ Active output |

Squirrel has been removed. The build now uses electron-forge package + electron-builder NSIS.

---

## How to Build

```powershell
.\scripts\build\build-win-cuda-121.ps1
```

Output: `frontend/out/installer/Erudi Setup <version>.exe`

---

## How to Test

Run `Erudi Setup <version>.exe`. It installs to `%APPDATA%\Local\Programs\erudi` by default (user-scope, no admin required) and creates a Start Menu shortcut.

The backend log file is written to `%TEMP%\erudi-backend.log`.

---

## What Was Fixed

### Bundle size: 6.5 GB → 2.3 GB

**File:** `backend/backend.spec`

**1. CUDA DLL filter** — PyInstaller's built-in torch hook auto-collects all of `torch/lib/*.dll` regardless of the spec. The filter strips them post-Analysis:

```python
_cuda_fragments = (
    "torch_cuda", "cublas", "cublaslt", "cufft", "curand",
    "cusolver", "cusolvermg", "cusparse", "cudnn", "nvrtc",
    "nvjitlink", "nvjpeg", "nvperf", "caffe2_nvrtc",
    # Small CUDA stubs — their deps (cublas, cudnn, etc.) are stripped above.
    # Leaving them causes [WinError 126] via shm.dll → c10_cuda → missing CUDA DLLs.
    "c10_cuda", "cudart", "cupti", "nvtoolsext",
)
a.binaries = [
    b for b in a.binaries
    if not any(frag in b[0].replace("\\", "/").lower() for frag in _cuda_fragments)
]
```

The embedder (sentence-transformers) runs CPU-only in the packaged build. GPU inference is handled by `llama-server.exe` which has its own CUDA binaries.

**2. Unused package exclusions** — packages pulled in transitively but never imported at runtime:

| Package | Size | Why excluded |
|---|---|---|
| `bitsandbytes` | 211 MB | Orphaned install, only in docstrings |
| `pyarrow` | 81 MB | Via `datasets` → `llmcompressor`, neither used at runtime |
| `pandas` | 17 MB | Same chain as pyarrow |
| `datasets` | 2 MB | Commented out in training stub |
| `llmcompressor` + `accelerate` + `compressed_tensors` | — | Never imported |

---

### ZIP crash [WinError 126]

**Symptom:** Backend process started but crashed immediately; `shm.dll` failed to load.

**Root cause:** The CUDA filter left behind small stubs (`c10_cuda.dll`, `cudart64_12.dll`, `cupti64_*.dll`, `nvToolsExt64_1.dll`). These exist in the bundle but their own dependencies (cublas, cudnn, etc.) were stripped. When torch loaded `shm.dll`, Windows tried to resolve the full dependency chain and failed.

**Fix:** Extended `_cuda_fragments` to include `c10_cuda`, `cudart`, `cupti`, `nvtoolsext`.

---

### Window not appearing on launch

**Symptom:** App visible in Task Manager but no window opens.

**Root cause:** The original architecture blocked window creation until the backend health check passed — 30s × 3 retries = up to 90 seconds before the window appeared. If the backend crashed early, the health check still ran its full timeout.

**Fix (2026-03-31):**
- Window is now created immediately on `app.whenReady()`
- Backend starts in the background; the renderer receives `backend-event` IPC messages for status
- Health check now aborts immediately if the backend process exits before becoming healthy (instead of waiting the full 30s)

---

## Why Squirrel Was Removed

Squirrel (`electron-winstaller` 5.4.0) silently fails for nupkgs over ~1 GB. It writes an empty `RELEASES` file (UTF-8 BOM only), then crashes with `System.InvalidOperationException: Source sequence doesn't contain any elements`. `electron-forge` swallows the exit code `-1` and reports success, leaving behind a 290 KB dummy Setup.exe.

---

## NSIS Migration (2026-04-01)

| | Squirrel (removed) | ZIP (old) | NSIS (current) |
|---|---|---|---|
| Single file installer | No | No (extract needed) | **Yes** |
| Handles 2+ GB bundles | No | Yes | **Yes** |
| Compression | ZIP | ZIP | LZMA2 (~30% smaller) |
| Auto-update | Built-in | None | `electron-updater` (future) |
| Admin required | No | No | No (user-scope default) |

**Approach — hybrid pipeline:**
1. `electron-forge package` bundles the app with webpack into `out/erudi-win32-x64/`
2. `electron-builder --prepackaged out/erudi-win32-x64` wraps it in NSIS

This keeps forge for webpack + macOS/Linux targets, and adds NSIS without touching any app code or the webpack pipeline.

**New files:**
- `frontend/electron-builder.yml` — NSIS config (icon, shortcuts, install dir option)
- `npm run dist:win` script — runs both steps in sequence
