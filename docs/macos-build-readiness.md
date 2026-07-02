# macOS Build Readiness

*Last updated: 2026-04-04 — after Windows build stabilization on `multi_backend_cuda`*

---

## TL;DR

The code changes made during Windows build stabilization are **safe for macOS**. No breaking changes were introduced. The macOS build does not exist yet — this document tracks what needs to be done to create it.

---

## What was changed and why it's safe

### `base_engine.py` — engine selection

The engine selector was updated to use `pynvml` instead of `torch.cuda.is_available()` for GPU detection (CPU-only torch always returns False for the latter).

The pynvml code is guarded behind `elif system in ("linux", "windows")`. macOS hits the `if system == "darwin"` branch, selects `MLX_Engine` (Apple Silicon) or `CPU_Engine` (Intel), and never touches pynvml.

```python
if system == "darwin":
    if "arm" in machine:
        llm_engine = MLX_Engine      # ← macOS ARM path, unchanged
    elif "x86" in machine:
        llm_engine = CPU_Engine      # ← macOS Intel path, unchanged
elif system in ("linux", "windows"):
    # pynvml detection — never reached on macOS
    ...
```

### `cpu_engine.py` — llama-server and converter fallbacks

Fallbacks to `cuda/bin/` were added for `_find_llama_server`, the converter script, and `llama-quantize`. Each fallback checks `.exists()` before returning it — if `cuda/bin/` doesn't exist (as on macOS), the function raises the same error as before. No regression.

The in-process converter (`_run_converter_inprocess`) and atomic GGUF rename were also added. Both are pure Python and cross-platform.

### `cuda_engine.py`

Only used when `CUDA_Engine` is selected (Windows/Linux with NVIDIA GPU). Never instantiated on macOS.

### `repository.py`, `services.py`, `context.py`

Pure Python bug fixes (conversation history tuple shape mismatch). No platform sensitivity.

### `forge.config.js`

macOS DMG and ZIP makers are intact and untouched. The Squirrel maker was removed (Windows-only) and replaced with electron-builder NSIS (also Windows-only). macOS build path is unaffected.

### `electron-builder.yml`

New file, Windows NSIS only. The macOS build uses `electron-forge` directly and never calls `electron-builder`.

### `main.js`

All macOS-specific platform guards are in place:
- `process.platform !== "darwin"` check for `window-all-closed` (macOS keeps app alive with no windows)
- `app.on("activate")` for dock re-open behavior
- macOS-specific app menu structure
- `process.platform === "darwin"` icon handling

---

## What needs to be done for the macOS build

### 1. `backend.spec` — pynvml hiddenimport

`backend.spec` now includes `"pynvml"` in `hiddenimports`. PyInstaller will error if the module isn't installed in the build venv, and pynvml is NVIDIA-only — it won't be present on a macOS venv.

**Fix:** Either create a separate `backend-mac.spec`, or make the import conditional:

```python
# in backend.spec hiddenimports list
*( ["pynvml"] if sys.platform != "darwin" else [] ),
```

### 2. Create a macOS build script

No `scripts/build/` script exists for macOS yet. It needs to:

1. Build the Python backend with PyInstaller (using a macOS-appropriate spec)
2. Copy `backend/dist/backend` into `frontend/backend/`
3. Run `electron-forge package` (for Apple Silicon: `--platform darwin --arch arm64`)
4. Run `electron-forge make` to produce the DMG

Optionally, if signing credentials are available in the environment, trigger notarization via the `osxSign`/`osxNotarize` config already present in `forge.config.js`.

### 3. MLX_Engine — verify still functional

`mlx_engine.py` was not touched in the Windows stabilization work, but it should be smoke-tested on Apple Silicon before publishing a macOS build:

- Engine selected at startup
- Model download + conversion pipeline
- Inference / streaming
- Knowledge Base (embedder on CPU)

### 4. `getDataDirectory()` in `main.js`

The current implementation returns `~/Library/Application Support/erudi` for all non-Windows platforms. This is correct for macOS. On Linux it would be wrong (`~/.config` is the convention), but that's a separate issue for the Linux build.

---

## How to resume

```
Branch: multi_backend_cuda (or wherever macOS work happens)

1. Create scripts/build/build-mac-silicon.sh
2. Fix backend.spec pynvml hiddenimport for macOS
3. Run the build on an Apple Silicon Mac
4. Smoke test: launch → download a model → chat → KB
5. Check $TMPDIR/erudi-backend.log for any engine selection issues
```
