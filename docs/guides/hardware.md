# Hardware Detection & Performance

How Erudi detects your hardware, which inference backend it picks, and what the
performance scores mean.

## Overview

Erudi detects the machine at startup and routes inference to the best available backend:

- **Apple Silicon (M1/M2/M3/M4)**: the **MLX** backend, running `mlx_vlm.server` on
  unified memory
- **NVIDIA GPUs**: the **CUDA** backend, running the CUDA build of `llama-server`
- **CPU fallback**: the CPU build of `llama-server`, on Windows and Linux

## How detection works

`BaseEngine.get_engine()` (`backend/src/engines/base_engine.py`) dispatches on
`platform.system()` and `platform.machine()`, and detects NVIDIA GPUs through `pynvml`
(not PyTorch):

1. macOS with an `arm` machine string → `MLX_Engine`
2. Windows or Linux where `pynvml.nvmlDeviceGetCount() > 0` → `CUDA_Engine`
3. Otherwise → `CPU_Engine`

```text
Priority: MLX > CUDA > CPU
```

Setting `ERUDI_FORCE_CPU=1` skips GPU detection entirely and returns `CPU_Engine`. It is
the supported way to exercise the CPU path on a GPU machine; see
[`backend/.env.example`](https://github.com/erudi-app/erudi/blob/main/backend/.env.example).

The chosen engine is logged at startup (`Engine chosen: ...`).

### What gets detected

**All backends**

- CPU model and core count
- Total and available RAM
- Disk space, total and available
- Operating system and architecture

**MLX (Apple Silicon)**

- Chip model (for example "M3 Max")
- GPU core count
- Neural Engine TOPS
- Memory bandwidth
- Unified memory capacity

**CUDA (NVIDIA)**

- GPU name
- CUDA core count and compute capability
- CUDA runtime version
- VRAM, total and available
- Memory bandwidth

**CPU**

- Logical core count
- Estimated memory bandwidth
- No GPU acceleration

## Performance scores

Each backend computes a 0-100 inference score from a weighted mix of compute, memory
bandwidth, memory capacity, and storage. There is a single score: inference. Erudi does
not train or fine-tune models.

### Score labels differ by backend

The numeric score is comparable across backends, but the **label thresholds are not
shared** — each engine has its own scale. Do not compare labels across machines with
different backends.

| Source | Scale |
|---|---|
| `MLX_Engine` (`backend/src/engines/mlx_engine.py`) | 80 Excellent · 60 Good · 40 Fair · 20 Poor · below Weak |
| `CPU_Engine` (`backend/src/engines/cpu_engine.py`) | 85 Amazing · 70 Excellent · 55 Very Good · 40 Good · 25 Medium · 10 Poor · below Terrible |
| `CUDA_Engine` (`backend/src/engines/cuda_engine.py`) | 90 Amazing · 80 Excellent · 70 Very High · 60 High · 50 Good · 40 Medium · 30 Bad · 20 Very Bad · 10 Poor · below Terrible |
| Hardware service (`backend/src/domains/hardware/services.py`) | 80 Excellent · 60 Good · 40 Fair · 20 Poor · below Weak |

The label the UI displays comes from the hardware service, applied to the boosted score.

### Boosted scores in the UI

The UI shows a **boosted score**: the raw score plus 20 points, capped at 100
(`Hardware_Service.calculate_boosted_scores`).

```text
Raw 65/100 → UI 85/100
Raw 82/100 → UI 100/100
```

Both values are returned by the API, so the boost is always visible for debugging.

### Recommended model size

Alongside the scores, the backend computes the model-size window the machine runs
comfortably at 4-bit, in billions of parameters: `recommended_param_min` and
`recommended_param_max` on `GET /erudi/hardware/app_startup`
(`recommended_param_range` in `backend/src/domains/hardware/services.py`).

The window is the smaller of two limits — what fits in usable memory after an overhead
reserve, and what is fast enough given memory bandwidth — clamped to a floor and a
ceiling. The model library uses it to tell you which catalog entries fit your machine.

## Refreshing hardware data

Hardware is re-detected on every app launch. Force a re-detection without restarting:

```bash
curl -X POST http://127.0.0.1:27182/erudi/hardware/refresh
```

Refresh after a RAM upgrade, a GPU change, or if the reported specs look wrong.

## API endpoints

### Startup summary

```bash
curl http://127.0.0.1:27182/erudi/hardware/app_startup
```

Returns the backend type, the boosted score and its label, the raw score, and the
recommended parameter range.

### Detailed diagnostics

```bash
curl http://127.0.0.1:27182/erudi/hardware/detailed
```

Returns the full profile with the score breakdown and both raw and boosted values.

### Refresh

```bash
curl -X POST http://127.0.0.1:27182/erudi/hardware/refresh
```

Forces re-detection and updates the stored profile.

## Backend differences

Expected relative throughput for a similarly sized model:

| Backend | Relative speed | Best for |
|---|---|---|
| MLX (Apple Silicon) | baseline | Macs; good balance of speed and memory |
| CUDA (recent NVIDIA GPU) | faster | Windows/Linux with a discrete GPU |
| CPU | much slower | machines with no supported GPU |

### Memory model

- **Apple Silicon** uses unified memory shared between CPU and GPU, which is why a Mac
  can hold a larger model than its GPU-only equivalent.
- **NVIDIA** uses dedicated VRAM; the CUDA engine offloads as many layers as fit and
  leaves the rest on the CPU.
- **CPU** uses system RAM only.

## Troubleshooting

### Hardware shows an error in the UI

1. Check the backend is running: `curl http://127.0.0.1:27182/erudi/health/`
2. Look for a `HARDWARE_ERROR` entry in `backend/logs/backend.log`
3. Force a refresh with `POST /erudi/hardware/refresh`

### The wrong backend was selected

```bash
# What the selector sees
python -c "import platform; print(platform.system(), platform.machine())"

# NVIDIA detection, the same way the backend does it
python -c "import pynvml; pynvml.nvmlInit(); print(pynvml.nvmlDeviceGetCount())"
```

- On macOS, MLX requires an `arm64` machine string. Running under Rosetta reports
  `x86_64` and the selector falls through.
- On Windows and Linux, CUDA requires `pynvml` to report at least one device; check the
  driver with `nvidia-smi`.
- Confirm `ERUDI_FORCE_CPU` is not set in your environment.

### A low score

The score reflects sustained inference throughput, so it is affected by available RAM,
background load, and thermal throttling. Closing other applications and improving cooling
both help. A mid-range score still runs the models inside your recommended parameter
range.

## FAQ

**Can I use MLX and CUDA at the same time?**
No. One backend is selected per session by the detection cascade.

**Can I choose the backend manually?**
Only `ERUDI_FORCE_CPU=1`, which forces the CPU engine. There is no UI switch.

**Does a higher score mean better answers?**
No. It means faster generation. Answer quality depends on the model.

**What if I have several GPUs?**
The CUDA backend uses the primary GPU.

## Technical details

- [Hardware Domain Reference](../reference/hardware.md) — schemas and endpoints
- [Engines Architecture](../dev/architecture/engines.md) — engine hierarchy and lifecycle
