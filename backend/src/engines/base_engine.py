import asyncio, threading, platform, importlib
from datetime import datetime, timedelta
from typing import Any, Optional, Tuple, Generator, Union, Type
from abc import ABC, abstractmethod, ABCMeta
from pathlib import Path

from src.core.exceptions import EngineException
from src.core.logging import logger

class EngineMeta(ABCMeta):
    def __repr__(cls):
        return f"LLM Engine: {cls.__name__}"
    
class BaseEngine(ABC, metaclass=EngineMeta):
    """Abstract base for all Engine backends (Singleton shared across subclasses)."""

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
        """Convert and quantize a HuggingFace model (already downloaded to local_hf_dir)
        into a directory ready for inference."""
        pass

    @classmethod
    @abstractmethod
    def get_model_and_tokenizer(
        cls,
        llm_id: str,
        llm_local_path: Union[str, Path],
        *args
    ) -> Tuple[Any, Any]:
        """Load or retrieve the model + tokenizer for this backend."""
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
        """Generate streamed text given a prompt. Yields the text tokens."""
        pass

    # ======================= COMMON INFRASTRUCTURE =======================
    @classmethod
    def get_engine(cls) -> Type["BaseEngine"] :
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
        """Generic cleanup: free memory and reset state."""
        if cls._model or cls._tokenizer:
            import gc
            logger.info(f"Cleaning up model {cls._model_id}")
            cls._model = cls._tokenizer = cls._model_id = cls._last_used = None
            gc.collect()

    @classmethod
    async def _cleanup_monitor(cls):
        while True:
            await asyncio.sleep(300)
            with cls._lock:
                if cls._should_cleanup():
                    cls.cleanup()

    @classmethod
    def start_cleanup_task(cls):
        if cls._cleanup_task is None:
            cls._cleanup_task = asyncio.create_task(cls._cleanup_monitor())
            logger.info("Started cleanup monitor")

    @classmethod
    def stop_cleanup_task(cls):
        if cls._cleanup_task is not None:
            cls._cleanup_task.cancel()
            cls._cleanup_task = None
            logger.info("Stopped cleanup monitor")