# -*- mode: python ; coding: utf-8 -*-
"""
Erudi Backend - PyInstaller spec for macOS Apple Silicon (arm64)

Bundles the FastAPI backend with MLX inference support into a
one-directory executable at backend/dist/backend/.

Prerequisites:
    cd backend
    venv/bin/pip install pyinstaller
    venv/bin/pyinstaller backend-mac-silicon.spec

Output:
    backend/dist/backend/backend   <- spawned by Electron main.js

The bundle root (dist/backend/) is set as ROOT_DIR by run.py, so all
relative paths (data/) resolve correctly at runtime.
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

spec_root = Path(SPECPATH)  # resolves to backend/

# ── Collected data / binaries ─────────────────────────────────────────────────
datas = []
binaries = []
hiddenimports = []

# torch: CPU tensor ops for the embedder (sentence-transformers).
# MLX handles LLM inference independently; torch is CPU-only here.
datas += collect_data_files("torch", includes=[
    "**/*.json",
    "**/*.yaml",
    "**/*.pyi",
])

# transformers: tokenizer configs, model cards, generation configs
datas += collect_data_files("transformers")

# sentence_transformers: module configs, pooling configs
datas += collect_data_files("sentence_transformers")

# tqdm: locale data
datas += collect_data_files("tqdm")

# filelock (used by transformers / huggingface_hub)
datas += collect_data_files("filelock")

# ── MLX: Apple Silicon inference framework ────────────────────────────────────
# collect_all captures compiled .so extensions, Metal shader kernels, and
# Python submodules that static analysis misses.
tmp_ret = collect_all("mlx")
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

tmp_ret = collect_all("mlx_lm")
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    ["run.py"],
    pathex=[str(spec_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + [
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
        "src.engines.mlx_engine",
        "src.engines.cpu_engine",
        "src.engines.embedder_engine",
        "src.launcher",
        "src.launcher.runtime_paths",
        "src.utils.file_processor",
        "src.utils.hf_model_metadata",
        "src.utils.kb_utils",
        "src.utils.prompt_utils",
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
        "pkg_resources",
        "importlib_metadata",
        "email.mime.multipart",
        "email.mime.text",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Windows-only / CUDA-only — not present on macOS
        "pynvml",
        "asyncio.windows_events",
        # llama-cpp is used for Windows inference only
        "llama_cpp",
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
    ],
    noarchive=False,
    optimize=0,
)

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
    upx=False,          # UPX breaks Metal/MLX binaries on macOS
    console=True,       # Must be True: Electron reads stdout JSON events
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="arm64",
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="backend",
)
