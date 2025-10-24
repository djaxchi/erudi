"""CPU engine for fallback inference using llama.cpp (STUB - UNDER DEVELOPMENT).

This module provides a CPU-only backend for systems without GPU acceleration:
- Uses llama.cpp for optimized CPU inference
- GGUF model format for quantization (4-bit, 5-bit, 8-bit)
- Threading optimization for multi-core CPUs
- Fallback when MLX (Mac Silicon) or CUDA (NVIDIA GPU) unavailable

Current Status:
    INCOMPLETE - This class is a stub. Full implementation pending.

Planned Features:
    - Load GGUF quantized models via llama-cpp-python
    - Multi-threaded inference with OpenMP/BLAS
    - Context window optimization for RAM constraints
    - Streaming generation with callback mechanism
    - Automatic thread count detection

Architecture (Planned):
    CPU Engine (Singleton):
    ┌───────────────────────────────────────────────────────────┐
    │ get_model_and_tokenizer()                                 │
    │  └─> Load GGUF model from disk → cache in RAM            │
    └───────────────────────────────────────────────────────────┘
                            ↓
    ┌───────────────────────────────────────────────────────────┐
    │ generate_stream()                                         │
    │  1. Tokenize prompt with llama.cpp tokenizer              │
    │  2. Generate with model(..., stream=True)                 │
    │  3. Yield tokens via callback iterator                    │
    └───────────────────────────────────────────────────────────┘

Example (Planned):
    ::

        from src.engines.cpu_engine import CPU_Engine

        model, tokenizer = CPU_Engine.get_model_and_tokenizer(
            llm_id="mistral-7b-q4",
            llm_local_path="/path/to/model.gguf"
        )

        for token in CPU_Engine.generate_stream(
            model, tokenizer, prompt,
            max_tokens=256, temperature=0.7
        ):
            print(token, end="")

Note:
    BaseEngine.get_engine() will automatically select CPU_Engine if:
    - System is not Mac Silicon (no MLX)
    - No CUDA-capable GPU detected (no CUDA_Engine)

    This ensures graceful degradation for unsupported hardware.

Warning:
    DO NOT USE IN PRODUCTION. Class is incomplete and will raise NotImplementedError.
    CPU inference is significantly slower than GPU (10-50x depending on model size).
    Use only as last resort fallback for testing/development.
"""

from src.engines.base_engine import BaseEngine

class CPU_Engine(BaseEngine):
    """Singleton Engine for models to run on llama.cpp.
    Fallback built to run on CPU Backends.
    """
    pass