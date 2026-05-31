# -*- mode: python ; coding: utf-8 -*-
"""
Erudi Backend - PyInstaller spec (cross-platform: Windows CUDA / macOS Apple Silicon)

Windows output:
    backend/dist/backend/backend.exe
    backend/dist/backend/artifacts/llama-cpp/cuda/bin/   <- llama-server.exe etc.

macOS output:
    backend/dist/backend/backend            <- spawned by Electron main.js
    (MLX inference via mlx_lm, no llama-server needed)

Build from backend/:
    Windows:  venv\\Scripts\\pyinstaller backend.spec
    macOS:    venv/bin/pyinstaller backend.spec
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"

spec_root = Path(SPECPATH)  # resolves to backend/

# ── Collected data / binaries ─────────────────────────────────────────────────
datas = []
binaries = []
hiddenimports = []

# torch: collect only config data files, NOT the CUDA DLLs.
datas += collect_data_files("torch", includes=[
    "**/*.json",
    "**/*.yaml",
    "**/*.pyi",
])

# transformers: tokenizer configs, model cards, generation configs
datas += collect_data_files("transformers")

# sentence_transformers: module configs, pooling configs
datas += collect_data_files("sentence_transformers")

# tqdm: needs its locale data on some systems
datas += collect_data_files("tqdm")

# filelock (used by transformers / huggingface_hub)
datas += collect_data_files("filelock")

# ── llama.cpp CUDA artifacts (Windows only) ───────────────────────────────────
if IS_WIN:
    llama_bin = spec_root / "artifacts" / "llama-cpp" / "cuda" / "bin"
    if llama_bin.exists():
        _dest = "artifacts/llama-cpp/cuda/bin"
        for _name in ("llama-server.exe", "llama-quantize.exe"):
            _f = llama_bin / _name
            if _f.exists():
                datas.append((str(_f), _dest))
        for _f in llama_bin.glob("convert*.py"):
            datas.append((str(_f), _dest))
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
_hidden_common = [
    # ── uvicorn internals
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
    # ── SQLAlchemy dialect
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
    # ── NVIDIA GPU detection (used by base_engine; graceful no-op on macOS)
    "pynvml",
    # ── Async I/O helpers
    "anyio",
    "anyio._backends._asyncio",
    "anyio._backends._trio",
    "sniffio",
    "h11",
    "exceptiongroup",
    "aiofiles",
    # ── Our own modules
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
    "src.engines.base_chat_server_engine",
    "src.engines.base_llama_cpp_engine",
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
    # ── stdlib
    "multiprocessing",
    "multiprocessing.util",
    "multiprocessing.managers",
    "asyncio",
    "pkg_resources",
    "importlib_metadata",
    "email.mime.multipart",
    "email.mime.text",
]

_hidden_windows = [
    "asyncio.windows_events",   # Windows-specific event loop policy
]

_hidden_macos = [
    "src.engines.mlx_engine",   # Apple Silicon MLX inference engine
    "mlx",
    "mlx_lm",
]

hiddenimports = _hidden_common
if IS_WIN:
    hiddenimports += _hidden_windows
if IS_MAC:
    hiddenimports += _hidden_macos

_excludes_common = [
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
    # Training / quantization packages not used at inference runtime
    "bitsandbytes",
    "llmcompressor",
    "compressed_tensors",
]

_excludes_windows = [
    "mlx",
    "mlx_lm",
]

_excludes_macos = [
    # CUDA packages are Windows-only; pynvml is imported but gracefully no-ops on Mac
]

excludes = _excludes_common
if IS_WIN:
    excludes += _excludes_windows
if IS_MAC:
    excludes += _excludes_macos

a = Analysis(
    ["run.py"],
    pathex=[str(spec_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

# ── Strip CUDA DLLs (Windows only) ────────────────────────────────────────────
# PyInstaller's torch hook auto-collects CUDA DLLs into a.binaries; they add
# ~3.8 GB but the packaged embedder runs CPU-only. Strip them on Windows.
if IS_WIN:
    _cuda_fragments = (
        "torch_cuda", "cublaslt", "cufft", "curand",
        "cusolver", "cusolvermg", "cusparse", "cudnn",
        "nvrtc", "nvjitlink", "nvjpeg", "nvperf",
        "cupti", "nvtoolsext",
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
    upx_exclude=[
        "*.dll",
        "vcruntime*.dll",
        "msvcp*.dll",
        "api-ms-*.dll",
        "ucrtbase.dll",
    ],
    name="backend",
)
