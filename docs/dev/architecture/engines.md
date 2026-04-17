# Engines Architecture

## Overview

The `src/engines/` directory contains all inference engine implementations for Erudi. Engines are responsible for loading models, generating text, and encoding embeddings.

## Engine Types

### LLM Engines

LLM engines implement the `BaseEngine` abstract class and provide text generation capabilities:

- **MLX_Engine**: Mac Silicon (Apple M1/M2/M3) using MLX framework
- **CUDA_Engine**: NVIDIA GPUs using CUDA + bitsandbytes
- **CPU_Engine**: Fallback CPU-only inference using transformers

#### Engine Selection

The appropriate engine is automatically selected based on hardware detection:

```python
from src.engines.base_engine import BaseEngine

# Automatic engine selection
engine = BaseEngine.get_engine()

# Manual engine selection
from src.engines.mlx_engine import MLX_Engine
engine = MLX_Engine()
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

| Engine | Hardware | Quantization | Framework |
|--------|----------|--------------|-----------|
| MLX    | Mac Silicon | 4-bit, 8-bit | MLX |
| CUDA   | NVIDIA GPU | 4-bit, 8-bit | bitsandbytes |
| CPU    | Any CPU | None | transformers |

### Embedder Engine

| Model | Dimensions | Size | Framework |
|-------|-----------|------|-----------|
| paraphrase-multilingual-MiniLM-L12-v2 | 384 | ~470 MB | sentence-transformers |

## Usage Patterns

### LLM Generation

```python
from src.core import config

# Use global engine from config
async for token in config.LLM_Engine.generate_stream(
    prompt="Hello, world!",
    params={"temperature": 0.7, "max_tokens": 100}
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

Engines check hardware capabilities at runtime:
- MLX: `platform.processor() == "arm"` and `platform.system() == "Darwin"`
- CUDA: `torch.cuda.is_available()`
- CPU: Always available as fallback

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
