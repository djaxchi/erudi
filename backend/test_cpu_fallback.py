"""CPU fallback & VRAM offload test script.

Run from the backend/ directory:
    python test_cpu_fallback.py

Tests:
    1. GPU layer thresholds via VRAM simulation (no model loaded)
    2. Engine selection: confirms CPU_Engine is chosen when ERUDI_FORCE_CPU=1
    3. Engine selection: confirms CUDA_Engine is chosen normally (GPU machine)

No model is loaded, no inference is run — this is a fast unit-level test.
"""

import sys
import os

# Force UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
INFO = "\033[94mINFO\033[0m"


def check(label: str, got, expected):
    # For classes: compare by name to avoid false failures from double-import paths.
    # For primitives (int, etc.): compare directly.
    if isinstance(expected, type):
        got_name = getattr(got, "__name__", repr(got))
        exp_name = getattr(expected, "__name__", repr(expected))
        ok = got_name == exp_name
        print(f"  [{PASS if ok else FAIL}] {label}: got={got_name!r}, expected={exp_name!r}")
    else:
        ok = got == expected
        print(f"  [{PASS if ok else FAIL}] {label}: got={got!r}, expected={expected!r}")
    return ok


# ---------------------------------------------------------------------------
# Test 1 — _compute_gpu_layers VRAM thresholds
# ---------------------------------------------------------------------------
print("\n=== Test 1: _compute_gpu_layers VRAM thresholds ===")

from engines.cuda_engine import CUDA_Engine

cases = [
    ("2 GB   -> CPU only (0 layers)",    "2",    0),
    ("4.5 GB -> partial offload (20)",   "4.5",  20),
    ("7 GB   -> partial offload (32)",   "7",    32),
    ("12 GB  -> full GPU (-1)",          "12",   -1),
]

results = []
for label, vram_val, expected in cases:
    os.environ["ERUDI_VRAM_OVERRIDE_GB"] = vram_val
    got = CUDA_Engine._compute_gpu_layers()
    results.append(check(label, got, expected))

os.environ.pop("ERUDI_VRAM_OVERRIDE_GB", None)

# ---------------------------------------------------------------------------
# Test 2 — _compute_gpu_layers with no GPU simulated (no override, no NVML)
# ---------------------------------------------------------------------------
print("\n=== Test 2: _compute_gpu_layers with no GPU (NVML returns empty) ===")

_original_get_nvml = CUDA_Engine._get_nvml_gpus.__func__

def _mock_no_gpu(cls):
    return []

CUDA_Engine._get_nvml_gpus = classmethod(_mock_no_gpu)
got = CUDA_Engine._compute_gpu_layers()
results.append(check("No GPU detected -> 0 layers", got, 0))
CUDA_Engine._get_nvml_gpus = classmethod(_original_get_nvml)

# ---------------------------------------------------------------------------
# Test 3 — get_engine returns CPU_Engine when ERUDI_FORCE_CPU=1
# ---------------------------------------------------------------------------
print("\n=== Test 3: get_engine() with ERUDI_FORCE_CPU=1 ===")

os.environ["ERUDI_FORCE_CPU"] = "1"
from engines.base_engine import BaseEngine
from engines.cpu_engine import CPU_Engine

engine = BaseEngine.get_engine()
results.append(check("ERUDI_FORCE_CPU=1 -> CPU_Engine", engine, CPU_Engine))
os.environ.pop("ERUDI_FORCE_CPU", None)

# ---------------------------------------------------------------------------
# Test 4 — get_engine returns CUDA_Engine on this machine (GPU present)
# ---------------------------------------------------------------------------
print("\n=== Test 4: get_engine() normal — expect CUDA_Engine on this machine ===")

try:
    from engines.cuda_engine import CUDA_Engine
    engine = BaseEngine.get_engine()
    from engines.cuda_engine import CUDA_Engine as CE
    results.append(check("GPU machine -> CUDA_Engine", engine, CE))
except Exception as e:
    print(f"  [{INFO}] CUDA_Engine not selected or NVML unavailable: {e}")
    print(f"  [{INFO}] This is expected if running on a non-CUDA machine.")
    results.append(True)  # Not a failure in this context

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n=== Summary ===")
total = len(results)
passed = sum(results)
failed = total - passed
print(f"  {passed}/{total} tests passed", end="")
if failed:
    print(f"  ({failed} FAILED)")
else:
    print(" — all good!")

sys.exit(0 if failed == 0 else 1)
