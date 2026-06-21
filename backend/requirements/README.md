# Erudi Backend — Requirements

Dependencies are split per platform/hardware to keep each build minimal and
reproducible. Composition is layered: an **entrypoint** pulls in shared **meta**
modules (`-r ...`).

## Layout

```
requirements/
├── entrypoints/
│   ├── dev/                  # prod + dev tools (pytest, ruff, …)
│   │   ├── mac-silicon.txt
│   │   ├── linux-cpu.txt
│   │   ├── linux-cuda.txt
│   │   ├── win-cpu.txt
│   │   └── win-cuda.txt
│   └── prod/                 # minimal runtime deps (one per platform, *-prod.txt)
├── meta/
│   ├── base.txt              # shared core: FastAPI, SQLAlchemy, pgserver,
│   │                         #   langchain, sentence-transformers, transformers (pinned 5.10.2)
│   ├── dev.txt               # pytest / ruff / black / mypy
│   ├── cpu.txt               # CPU torch (official CPU index) + gguf — REUSED by the CUDA entrypoints
│   ├── cuda-specs.txt        # CUDA-only non-torch bits (pynvml). No torch+cuXXX.
│   ├── cuda-win-specs.txt    # Windows CUDA build tools (cmake)
│   ├── linux-specs.txt
│   ├── mac-silicon-specs.txt # MLX (mlx-vlm)
│   └── win-specs.txt         # Windows-only (currently none)
└── freezes/                  # optional pinned freezes
```

## Key design notes

- **Inference is llama.cpp / MLX, not torch.** torch is only pulled (CPU build)
  by sentence-transformers for the e5 KB embeddings. There is **no torch+CUDA**:
  the CUDA build uses **CPU torch** plus a CUDA-compiled `llama-server` binary
  (built by `scripts/dev/backend/build-llamacpp-cuda-*`). The CUDA toolkit version
  lives in the **binary build**, not in pip — which is why there is a single
  `cuda` entrypoint per OS (no 118/121 split anymore).
- **transformers is pinned once in `base.txt` (5.10.2)** for every platform. It is
  coupled to torch (5.10.2 imports `torch.float8_e8m0fnu`, needing torch>=2.7).
- Fine-tuning deps (peft/accelerate/datasets/bitsandbytes) were removed — the
  feature is unimplemented dead code (see the fine-tuning cleanup issue).

## Usage

```bash
# Dev (with testing/linting tools)
pip install -r requirements/entrypoints/dev/<platform>.txt
# Prod (minimal)
pip install -r requirements/entrypoints/prod/<platform>-prod.txt
```

Or use the platform setup scripts in `scripts/dev/backend/` (they default to prod
in CI; set `INSTALL_TYPE=dev|prod` to force).

## Adding a dependency

- Shared (all platforms) → `meta/base.txt`
- Dev tool → `meta/dev.txt`
- Platform / hardware-specific → the matching `meta/*-specs.txt`
