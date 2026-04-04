# -*- mode: python ; coding: utf-8 -*-
"""
Erudi Backend - PyInstaller spec for Windows CUDA 12.1

Bundles the FastAPI backend with CUDA 12.1 inference support into a
one-directory executable at backend/dist/backend/.

Prerequisites:
    cd backend
    venv\\Scripts\\pip install pyinstaller
    venv\\Scripts\\pyinstaller backend.spec

Output:
    backend/dist/backend/backend.exe   ← spawned by Electron main.js
    backend/dist/backend/artifacts/llama-cpp/cuda/bin/  ← llama-server.exe etc.

The bundle root (dist/backend/) is set as ROOT_DIR by run.py, so all
relative paths (artifacts/, data/) resolve correctly at runtime.
"""

import sys
from pathlib import Path

# PyInstaller hook utilities
from PyInstaller.utils.hooks import collect_all, collect_data_files

spec_root = Path(SPECPATH)  # resolves to backend/

# ── Collected data / binaries ─────────────────────────────────────────────────
datas = []
binaries = []
hiddenimports = []

# torch: collect only config data files, NOT the CUDA DLLs.
# collect_dynamic_libs("torch") would pull in cublas, cudnn, cufft, etc. (5-6 GB)
# which would make the installer unmanageably large (7+ GB).
# The embedder (sentence-transformers) runs on CPU in the packaged build — it is
# fast enough for 384-dim encoding and llama-server.exe handles GPU LLM inference
# independently with its own CUDA binaries. If CUDA DLLs are absent, torch
# reports cuda.is_available()=False and Embedder_Engine._select_device() falls
# back to "cpu" via its existing exception-handling path.
datas    += collect_data_files("torch", includes=[
    "**/*.json",       # model configs
    "**/*.yaml",       # configs
    "**/*.pyi",        # type stubs (small)
])

# transformers: tokenizer configs, model cards, generation configs
datas += collect_data_files("transformers")

# sentence_transformers: module configs, pooling configs
datas += collect_data_files("sentence_transformers")

# tqdm: needs its locale data on some systems
datas += collect_data_files("tqdm")

# filelock (used by transformers / huggingface_hub)
datas += collect_data_files("filelock")

# ── llama.cpp CUDA artifacts ──────────────────────────────────────────────────
# Only include the files actually used at runtime — NOT the 50+ test/bench
# binaries (each ~870 MB statically linked), which would bloat the bundle by 45 GB.
llama_bin = spec_root / "artifacts" / "llama-cpp" / "cuda" / "bin"
if llama_bin.exists():
    _dest = "artifacts/llama-cpp/cuda/bin"
    # Runtime binaries
    for _name in ("llama-server.exe", "llama-quantize.exe"):
        _f = llama_bin / _name
        if _f.exists():
            datas.append((str(_f), _dest))
    # HF→GGUF conversion scripts
    for _f in llama_bin.glob("convert*.py"):
        datas.append((str(_f), _dest))
    # gguf-py Python package (needed by conversion scripts)
    _gguf = llama_bin / "gguf-py"
    if _gguf.exists():
        datas.append((str(_gguf), f"{_dest}/gguf-py"))
else:
    import warnings
    warnings.warn(
        f"llama-cpp CUDA binaries not found at {llama_bin}. "
        "Run scripts/dev/backend/build-llamacpp-cuda-win.ps1 first."
    )

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    ["run.py"],
    pathex=[str(spec_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        # ── uvicorn internals (loaded via importlib, missed by static analysis)
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.lifespan",
        "uvicorn.lifespan.off",
        "uvicorn.lifespan.on",
        # ── SQLAlchemy dialect (loaded by string at connect time)
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.dialects.sqlite.pysqlite",
        "sqlalchemy.ext.asyncio",
        "aiosqlite",
        # ── Starlette / FastAPI internals
        "starlette.routing",
        "starlette.responses",
        "starlette.requests",
        "starlette.middleware.cors",
        "starlette.middleware.base",
        # ── Pydantic v2
        "pydantic",
        "pydantic.v1",
        "pydantic_core",
        # ── NVIDIA GPU detection (used by base_engine and cuda_engine for engine selection)
        "pynvml",
        # ── Async I/O helpers
        "anyio",
        "anyio._backends._asyncio",
        "anyio._backends._trio",
        "sniffio",
        "h11",
        "exceptiongroup",
        "aiofiles",
        # ── Our own modules (some loaded dynamically via BaseEngine.get_engine)
        "src.main",
        "src.core.api",
        "src.core.config",
        "src.core.exceptions",
        "src.core.logging",
        "src.core.health",
        "src.config.secrets",
        "src.database.core",
        "src.database.seed",
        "src.entities.Conversation",
        "src.entities.DownloadJob",
        "src.entities.HardwareProfile",
        "src.entities.KBJob",
        "src.entities.KnowledgeBase",
        "src.entities.Llm",
        "src.entities.Message",
        "src.entities.StartupVariables",
        "src.entities.TrainingJob",
        "src.entities.VectorStore",
        "src.engines.base_engine",
        "src.engines.cuda_engine",
        "src.engines.cpu_engine",
        "src.engines.embedder_engine",
        "src.launcher",
        "src.launcher.runtime_paths",
        "src.utils.file_processor",
        "src.utils.hf_model_metadata",
        "src.utils.kb_utils",
        "src.utils.prompt_utils",
        "src.utils.secrets",
        "src.domains.arena.endpoints",
        "src.domains.arena.repository",
        "src.domains.arena.services",
        "src.domains.arena.schemas",
        "src.domains.conversations.endpoints",
        "src.domains.conversations.repository",
        "src.domains.conversations.services",
        "src.domains.conversations.schemas",
        "src.domains.conversations.utils.cache",
        "src.domains.conversations.utils.cache_types",
        "src.domains.conversations.utils.context",
        "src.domains.conversations.utils.embedding",
        "src.domains.conversations.utils.prompt",
        "src.domains.hardware.endpoints",
        "src.domains.hardware.repository",
        "src.domains.hardware.services",
        "src.domains.hardware.schemas",
        "src.domains.knowledge_base.endpoints",
        "src.domains.knowledge_base.repository",
        "src.domains.knowledge_base.services",
        "src.domains.knowledge_base.schemas",
        "src.domains.llms.endpoints",
        "src.domains.llms.repository",
        "src.domains.llms.services",
        "src.domains.llms.schemas",
        "src.domains.startup.endpoints",
        "src.domains.startup.repository",
        "src.domains.startup.schemas",
        "src.domains.training.endpoints",
        "src.domains.training.services",
        "src.domains.training.schemas",
        # ── ML / inference
        "numpy",
        "faiss",
        "transformers",
        "sentence_transformers",
        "huggingface_hub",
        "tokenizers",
        "pypdf",
        "tqdm",
        "requests",
        "httpx",
        # ── stdlib occasionally missed by PyInstaller
        "multiprocessing",
        "multiprocessing.util",
        "multiprocessing.managers",
        "asyncio",
        "asyncio.windows_events",     # Windows-specific policy
        "pkg_resources",
        "importlib_metadata",
        "email.mime.multipart",
        "email.mime.text",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Mac-only frameworks — never present on Windows
        "mlx",
        "mlx_lm",
        # Heavy GUI / data science packages not used at runtime
        "matplotlib",
        "IPython",
        "jupyter",
        "notebook",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "tkinter",
        "_tkinter",
        "cv2",
        "wx",
        # Test tooling
        "pytest",
        "black",
        "ruff",
        "mypy",
        # Training / quantization packages — not used at inference runtime.
        # bitsandbytes: orphaned install (no importer), transformers auto-detects
        #   it and would try to pull it in; excluding saves 211 MB.
        # datasets / pyarrow / pandas / accelerate: pulled back in because
        #   sentence_transformers imports them transitively at package level
        #   (model_card → datasets, cross_encoder trainer → peft → accelerate).
        # llmcompressor + compressed_tensors: never imported, safe to exclude.
        "bitsandbytes",
        "llmcompressor",
        "compressed_tensors",
        "compressed_tensors",
    ],
    noarchive=False,
    optimize=0,
)

# ── Strip CUDA DLLs that PyInstaller's built-in torch hook auto-collects ───────
# The hook pulls torch/lib/*.dll into a.binaries regardless of what the spec
# says (even without collect_dynamic_libs). For the packaged build the embedder
# runs CPU-only; torch_cuda, cublas*, cudnn*, cufft*, cusparse*, curand*,
# nvrtc*, etc. add ~3.8 GB but are never loaded. We keep torch_cpu.dll and
# torch_python.dll which sentence-transformers needs for CPU inference.
_cuda_fragments = (
    "torch_cuda", "cublaslt", "cufft", "curand",
    "cusolver", "cusolvermg", "cusparse", "cudnn",
    "nvrtc", "nvjitlink", "nvjpeg", "nvperf",
    # cublas64_12.dll kept — torch.dll statically imports it (108 MB, required)
    # caffe2_nvrtc.dll kept — torch_cpu.dll statically imports it (17 KB, required)
    # Profiling/tooling stubs — no runtime code path uses these.
    "cupti", "nvtoolsext",
    # NOTE: shm.dll is kept — torch_python.dll statically imports it.
    # With CPU-only torch it has no CUDA dependencies (15 KB, harmless).
    # NOTE: c10_cuda, cudart, cublas, cublasLt are not present in CPU torch
    # so there is nothing to strip for those.
)
a.binaries = [
    b for b in a.binaries
    if not any(frag in b[0].replace("\\", "/").lower() for frag in _cuda_fragments)
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,      # Must be True: Electron reads stdout JSON events
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    # Do NOT UPX system DLLs — they will break
    upx_exclude=[
        "*.dll",
        "vcruntime*.dll",
        "msvcp*.dll",
        "api-ms-*.dll",
        "ucrtbase.dll",
    ],
    name="backend",
)
