"""Abstract base engine for multi-backend LLM inference.

This module provides the foundation for Erudi's multi-engine architecture,
supporting MLX (Apple Silicon), CUDA (NVIDIA GPUs), and CPU fallback.
The engine abstraction enables consistent model loading, quantization,
and streaming inference across different hardware backends.

Fonctionnalités:
- Automatic engine selection based on platform and hardware
- Singleton pattern with shared model state across requests
- Automatic memory cleanup after idle timeout
- Streaming token generation API
- HuggingFace model conversion and quantization

Architecture:
    BaseEngine (ABC)
    ├── MLX_Engine (Apple Silicon)
    ├── CUDA_Engine (NVIDIA GPUs)
    └── CPU_Engine (Fallback)

Examples:
    Get appropriate engine for current platform:
        from src.engines.base_engine import BaseEngine
        engine_class = BaseEngine.get_engine()
        model, tokenizer = engine_class.get_model_and_tokenizer(
            llm_id="1",
            llm_local_path="backend/data/models/llama-7b"
        )
    
    Stream tokens:
        for token in engine_class.generate_stream(
            model, tokenizer,
            prompt=[{"role": "user", "content": "Hello"}],
            max_tokens=100,
            temperature=0.7,
            top_p=0.9
        ):
            print(token, end="", flush=True)

"""

import asyncio, threading, platform, importlib
from datetime import datetime, timedelta
from typing import Any, Optional, Tuple, Generator, Union, Type
from abc import ABC, abstractmethod, ABCMeta
from pathlib import Path

from src.core.exceptions import EngineException
from src.core.logging import logger


class EngineMeta(ABCMeta):
    """Metaclass for Engine classes with custom repr."""
    
    def __repr__(cls):
        """Return human-readable engine class name.
        
        Returns:
            String representation like "LLM Engine: MLX_Engine".

        """
        return f"LLM Engine: {cls.__name__}"
    

class BaseEngine(ABC, metaclass=EngineMeta):
    """Abstract base class for all LLM inference engines.
    
    Implements singleton pattern with shared model state, automatic cleanup,
    and platform-aware engine selection. Subclasses must implement backend-
    specific model loading and inference methods.
    
    Class Attributes:
        _model: Currently loaded model instance (shared across all engines).
        _tokenizer: Currently loaded tokenizer instance.
        _model_id: ID of the currently loaded model.
        _last_used: Timestamp of last model access for cleanup tracking.
        _lock: Thread lock for safe concurrent access.
        _cleanup_task: Async task monitoring idle time.
        _max_idle_time: Seconds before automatic memory cleanup (default: 300).
        MODEL_MAPPING: Dictionary mapping model architectures to classes.
    
    Note:
        Do not instantiate directly. Use get_engine() to obtain the appropriate
        engine class, then call class methods for operations.

    """

    # --- Global shared state (unique across all engines) ---
    _model: Optional[Any] = None
    _tokenizer: Optional[Any] = None
    _model_id: Optional[int] = None
    _last_used: Optional[datetime] = None
    _lock = threading.Lock()

    # --- Lifecycle management ---
    _cleanup_task = None
    _max_idle_time = 300  # 5 min

    MODEL_MAPPING : dict = {}

    def __init__(self):
        """Prevent direct instantiation.
        
        Raises:
            RuntimeError: Always raised as engines use class methods only.

        """
        raise RuntimeError("Use the methods instead of instantiating")


    @classmethod
    def __repr__(cls):
        return f"LLM Engine: {cls.__name__}"

    # ======================= COMMON API CONTRACT =======================
    @classmethod
    @abstractmethod
    def quant_and_save_from_hf_format(
        cls,
        local_hf_path: Union[str, Path],
        local_dest_path: Union[str, Path],
        quantize: bool = True,
        q_bits: str = "4",
        *args
    ) -> None:
        """Convert and quantize HuggingFace model to engine-specific format.
        
        Downloads or uses a local HuggingFace model, applies quantization if
        requested, and saves in the format required by this engine 
        
        Args:
            local_hf_path: Path to HuggingFace model directory.
            local_dest_path: Destination directory for converted model.
            quantize: Whether to apply quantization (default: True).
            q_bits: Quantization bits, e.g., "4", "8" (default: "4").
            *args: Engine-specific additional arguments.
            
        Raises:
            EngineException: If conversion or quantization fails.
            FileNotFoundError: If source model path doesn't exist.
            
        Note:
            Implementation is backend-specific. MLX uses mlx-lm convert,
            CUDA uses bitsandbytes, CPU may skip quantization.

        """
        pass

    @classmethod
    @abstractmethod
    def get_model_and_tokenizer(
        cls,
        llm_id: str,
        llm_local_path: Union[str, Path],
        *args
    ) -> Tuple[Any, Any]:
        """Load or retrieve cached model and tokenizer for inference.
        
        Implements singleton pattern: returns cached model if already loaded
        for the given llm_id, otherwise loads from disk. Thread-safe.
        
        Args:
            llm_id: Unique identifier for the model (used for caching).
            llm_local_path: Path to the model directory on disk.
            *args: Engine-specific loading arguments (e.g., device, dtype).
            
        Returns:
            Tuple of (model, tokenizer) ready for inference.
            
        Raises:
            EngineException: If model loading fails.
            FileNotFoundError: If model path doesn't exist.
            
        Examples:
            from src.engines.base_engine import BaseEngine
            engine = BaseEngine.get_engine()
            model, tokenizer = engine.get_model_and_tokenizer(
                llm_id="1",
                llm_local_path="backend/data/models/llama-7b"
            )

        """
        pass

    @classmethod
    @abstractmethod
    def generate_stream(
        cls,
        model: Any,
        tokenizer: Any,
        prompt: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        top_p: float,
        *args
    ) -> Generator[str, None, None]:
        """Generate text tokens in streaming fashion.
        
        Yields tokens one-by-one as they are generated, enabling real-time
        response streaming to clients.
        
        Args:
            model: Loaded model instance from get_model_and_tokenizer.
            tokenizer: Loaded tokenizer instance.
            prompt: Chat-style messages, e.g., [{"role": "user", "content": "Hi"}].
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature (0.0 = greedy, higher = more random).
            top_p: Nucleus sampling threshold (0.0-1.0).
            *args: Engine-specific generation parameters.
            
        Yields:
            String tokens as they are generated.
            
        Raises:
            EngineException: If inference fails (OOM, model error, etc.).
            RuntimeError: If model or tokenizer is not initialized.
            
        Examples:
            for token in engine.generate_stream(
                model, tokenizer,
                prompt=[{"role": "user", "content": "Hello"}],
                max_tokens=100,
                temperature=0.7,
                top_p=0.9
            ):
                print(token, end="", flush=True)

        """
        pass

    # ======================= COMMON INFRASTRUCTURE =======================
    @classmethod
    def get_engine(cls) -> Type["BaseEngine"]:
        """Select and return appropriate engine class for current platform.
        
        Automatically detects OS and hardware to choose the optimal backend:
        - macOS ARM (M1/M2/M3): MLX_Engine
        - macOS Intel: CPU_Engine
        - Linux/Windows with CUDA: CUDA_Engine
        - Linux/Windows without CUDA: CPU_Engine
        
        Returns:
            The engine class (not an instance) appropriate for this system.
            
        Raises:
            EngineException: If no suitable engine can be determined.
            
        Examples:
            from src.engines.base_engine import BaseEngine
            engine_class = BaseEngine.get_engine()
            print(f"Using: {engine_class}")  # e.g., "LLM Engine: MLX_Engine"

        """
        from src.engines.mlx_engine import MLX_Engine
        from src.engines.cpu_engine import CPU_Engine
        from src.engines.cuda_engine import CUDA_Engine

        system = platform.system().lower()     # mac, linux, windows
        machine = platform.machine().lower()   # arm64, x86_64, etc.
        llm_engine = None

        try:
            if system == "darwin": # MacOS
                if "arm" in machine:
                    llm_engine = MLX_Engine
                elif "x86" in machine:
                    llm_engine = CPU_Engine
            elif system in ("linux", "windows"):
                try:
                    torch = importlib.import_module("torch")
                except:
                    raise
                if torch.backends.cuda.is_built() and torch.cuda.is_available():
                    llm_engine = CUDA_Engine
                else:
                    llm_engine = CPU_Engine
                    logger.info(f"System: {system} and CUDA not availabl.")
            logger.info(f"Engine chosen: {llm_engine}")
            if llm_engine is None:
                raise
            return llm_engine
        except Exception as e:
            raise EngineException(message="Error selecting the LLM Engine.", trace=e)

    @classmethod
    def _should_cleanup(cls) -> bool:
        if cls._last_used is None or cls._model is None:
            return False
        idle_time = datetime.now() - cls._last_used
        return idle_time > timedelta(seconds=cls._max_idle_time)

    @classmethod
    def _should_reload_model(cls, llm_id: str) -> bool:
        return llm_id == cls._model_id and cls._model is not None and cls._tokenizer is not None

    @classmethod
    def _return_cached_model_and_tokenizer(cls) -> Tuple[Any, Any]:
        cls._last_used = datetime.now()
        logger.info(f"Using cached model {cls._model_id}")
        return cls._model, cls._tokenizer
    
    @classmethod
    def cleanup(cls) -> None:
        """Free model and tokenizer from memory, reset state.
        
        Releases GPU/CPU memory occupied by the model and tokenizer,
        resets all cached state. Called automatically after idle timeout
        or manually when switching models.
        
        Note:
            Thread-safe. Can be called explicitly or by cleanup monitor.
            Calls garbage collector to ensure memory is freed.

        """
        if cls._model or cls._tokenizer:
            import gc
            logger.info(f"Cleaning up model {cls._model_id}")
            cls._model = cls._tokenizer = cls._model_id = cls._last_used = None
            gc.collect()

    @classmethod
    async def _cleanup_monitor(cls):
        """Background task monitoring idle time and triggering cleanup.
        
        Runs every 300 seconds, checks if model has been idle longer than
        _max_idle_time, and calls cleanup() if threshold exceeded.
        
        Note:
            Internal method. Do not call directly. Use start_cleanup_task().

        """
        while True:
            await asyncio.sleep(300)
            with cls._lock:
                if cls._should_cleanup():
                    cls.cleanup()

    @classmethod
    def start_cleanup_task(cls):
        """Start the automatic cleanup monitoring task.
        
        Creates an async task that periodically checks for idle models
        and frees memory. Should be called once during application startup.
        
        Note:
            Idempotent - calling multiple times has no effect if task already running.
            
        Examples:
            from src.engines.base_engine import BaseEngine
            engine = BaseEngine.get_engine()
            engine.start_cleanup_task()

        """
        if cls._cleanup_task is None:
            cls._cleanup_task = asyncio.create_task(cls._cleanup_monitor())
            logger.info("Started cleanup monitor")

    @classmethod
    def stop_cleanup_task(cls):
        """Stop the automatic cleanup monitoring task.
        
        Cancels the cleanup monitor task. Should be called during application
        shutdown to gracefully stop background tasks.
        
        Note:
            Idempotent - calling when no task is running has no effect.
            
        Examples:
            from src.engines.base_engine import BaseEngine
            engine = BaseEngine.get_engine()
            engine.stop_cleanup_task()

        """
        if cls._cleanup_task is not None:
            cls._cleanup_task.cancel()
            cls._cleanup_task = None
            logger.info("Stopped cleanup monitor")