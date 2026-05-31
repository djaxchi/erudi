# Engines Architecture

## Overview

The `src/engines/` directory contains all inference engine implementations for Erudi. Engines are responsible for loading models, generating text, and encoding embeddings.

## Engine Types

### LLM Engines

LLM engines implement the `BaseEngine` abstract class. All three follow the
same pattern: they spawn an OpenAI-compatible HTTP server in a child
process and talk to it over `http://127.0.0.1:<port>/v1/chat/completions`
(streaming SSE).

- **MLX_Engine** (Mac Silicon M1/M2/M3/M4): spawns `mlx_lm.server` via
  `multiprocessing.Process(target=run_mlx_server, ...)`. Child port range
  9080+.
- **CUDA_Engine** (Windows/Linux + NVIDIA): spawns the `llama-server`
  binary (CUDA build) via `subprocess.Popen`. Child port range 8080+.
- **CPU_Engine** (Windows / Linux / macOS Intel): spawns the same
  `llama-server` binary (CPU build) via `subprocess.Popen`. Child port
  range 8080+.

`multiprocessing.Process` is required for MLX because PyInstaller frozen
builds have no Python interpreter at `sys.executable` to pass `-m` to;
`mp.spawn` (configured in `backend/run.py:143-160`) re-executes the
binary in child mode. CPU/CUDA can use `Popen` because the
`llama-server` binary is bundled in
`backend/artifacts/llama-cpp/<cpu|cuda>/bin/`.

#### Engine Selection

The appropriate engine is automatically selected based on hardware detection:

```python
from src.engines.base_engine import BaseEngine

# Auto-select engine class (not an instance — engines expose only
# classmethods; instantiation is intentionally blocked).
engine_class = BaseEngine.get_engine()

# Set globally for the lifetime of the FastAPI app (see core/api.py:lifespan).
from src.core import config
config.LLM_Engine = engine_class
```

### Embedder Engine

The `Embedder_Engine` is a singleton that manages the sentence transformer model used for:
- Knowledge base vector creation
- Semantic search in conversations
- Query embedding for RAG

```python
from src.engines.embedder_engine import Embedder_Engine

# Get embedder instance (lazy loaded)
embedder = Embedder_Engine.get_embedder()

# Encode text
embedding = embedder.encode("Sample text")

# Cleanup to free memory
Embedder_Engine.cleanup()
```

## Architecture Principles

### Separation of Concerns

- **Engines** (`src/engines/`): Inference backends (LLM generation, text embedding)
- **Utils** (`src/utils/`): Pure utility functions (prompts, file processing)
- **Domains** (`src/domains/`): Business logic using engines and utils

### Why Embedder is an Engine

The `Embedder_Engine` is in `src/engines/` (not `src/utils/`) because:

1. **Inference Backend**: Loads and runs ML models (sentence transformer)
2. **Memory Management**: Requires explicit lifecycle management (load/cleanup)
3. **Hardware Dependent**: Performance varies by backend (GPU/CPU)
4. **Singleton Pattern**: Prevents multiple instances in memory
5. **Architectural Consistency**: Aligns with other engine patterns

## Model Specifications

### LLM Engines

| Engine | Hardware | Model format | Inference backend | Child launch |
|--------|----------|--------------|--------------------|--------------|
| MLX    | Mac Silicon | MLX 4-bit (mlx-community/* repos) | `mlx_lm.server` | `mp.Process` |
| CUDA   | NVIDIA GPU | GGUF (Q4_K_M default, Q5_K_M, Q8_0, FP16 fallback) | `llama-server` binary | `subprocess.Popen` |
| CPU    | Any CPU | GGUF (same as CUDA) | `llama-server` binary | `subprocess.Popen` |

### Embedder Engine

| Model | Dimensions | Size | Framework |
|-------|-----------|------|-----------|
| paraphrase-multilingual-MiniLM-L12-v2 | 384 | ~470 MB | sentence-transformers |

## Usage Patterns

### LLM Generation

```python
from src.core import config

# Load (or reuse cached) model handle; spawns subprocess if first call.
model, tokenizer = config.LLM_Engine.get_model_and_tokenizer(
    llm_id=llm.id,
    llm_local_path=llm.link,
)

# Sync generator — wrapped by Starlette via iterate_in_threadpool when
# passed to StreamingResponse.
for token in config.LLM_Engine.generate_stream(
    model=model,
    tokenizer=tokenizer,
    prompt=[{"role": "user", "content": "Hello, world!"}],
    max_tokens=100,
    temperature=0.7,
    top_p=0.9,
):
    print(token, end="", flush=True)
```

### Embedder

```python
from src.engines.embedder_engine import Embedder_Engine
import numpy as np

# Load embedder
embedder = Embedder_Engine.get_embedder()

# Encode for KB
texts = ["Document 1", "Document 2"]
embeddings = embedder.encode(texts, convert_to_tensor=True)

# Convert to numpy for FAISS
emb_np = embeddings.detach().cpu().numpy().astype("float32")

# Cleanup
Embedder_Engine.cleanup()
```

## Migration Guide

### From utils.inference_utils to engines.embedder_engine

**Old code (deprecated):**
```python
from src.utils.inference_utils import EmbedderService

embedder = EmbedderService.get_embedder()
EmbedderService.cleanup()
```

**New code (preferred):**
```python
from src.engines.embedder_engine import Embedder_Engine

embedder = Embedder_Engine.get_embedder()
Embedder_Engine.cleanup()
```

**Backward compatibility:**
The old import still works via re-export in `src/utils/inference_utils.py`, but will be removed in v1.0.0.

## Performance Considerations

### Memory Management

- **LLM Engines**: Models stay loaded until engine replacement
- **Embedder**: Call `cleanup()` after batch operations to free ~470 MB

### Batching

- **Embedder**: Encode in batches for better GPU utilization
- **LLM**: Use streaming for responsive UX

### Hardware Detection

`BaseEngine.get_engine()` (base_engine.py:507) dispatches at startup:
- macOS ARM (`platform.system() == "Darwin"` and `"arm" in platform.machine()`) → MLX_Engine
- macOS Intel → CPU_Engine
- Linux/Windows with CUDA (`pynvml.nvmlDeviceGetCount() > 0`) → CUDA_Engine
- Otherwise → CPU_Engine

Set `ERUDI_FORCE_CPU=1` to bypass GPU detection entirely.

## Testing

Test engines with mocks to avoid loading actual models:

```python
import pytest
from unittest.mock import MagicMock

def test_embedder_cleanup(monkeypatch):
    mock_embedder = MagicMock()
    monkeypatch.setattr(
        "src.engines.embedder_engine.Embedder_Engine._instance",
        mock_embedder
    )
    
    Embedder_Engine.cleanup()
    assert Embedder_Engine._instance is None
```

## Error Handling

Engines should raise specific exceptions from `src.core.exceptions`:

```python
from src.core.exceptions import ModelLoadError, InferenceError

try:
    embedder = Embedder_Engine.get_embedder()
except Exception as e:
    logger.error(f"Failed to load embedder: {e}")
    raise ModelLoadError(f"Embedder initialization failed: {e}") from e
```

## See Also

- [Base Engine Documentation](./base_engine.md)
- [Multi-Engine Architecture](./multi_engine.md)
- [Model Lifecycle](./model_lifecycle.md)
