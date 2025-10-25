"""MLX engine for Apple Silicon inference using Metal Performance Shaders.

This module implements the MLX backend for local LLM inference on Mac devices
with M1/M2/M3 chips. It provides:
- 4-bit quantization for memory efficiency
- Metal GPU acceleration via MLX framework
- Thread-safe model loading and generation
- Automatic model caching and cleanup

Architecture:
    MLX Engine (Singleton):
    ┌───────────────────────────────────────────────────────────┐
    │ get_model_and_tokenizer()                                 │
    │  └─> Load quantized model from disk → cache in memory    │
    └───────────────────────────────────────────────────────────┘
                            ↓
    ┌───────────────────────────────────────────────────────────┐
    │ generate_stream()                                         │
    │  1. Apply chat template                                   │
    │  2. Configure sampler (temp, top_p, top_k)                │
    │  3. Stream tokens via mlx_lm.stream_generate()            │
    │  4. Update last_used timestamp                            │
    └───────────────────────────────────────────────────────────┘
                            ↓
    ┌───────────────────────────────────────────────────────────┐
    │ Cleanup Task (30s interval)                               │
    │  └─> Free model if idle > 300s                            │
    └───────────────────────────────────────────────────────────┘

Quantization Mapping:
    Maps HuggingFace model IDs to MLX-quantized 4-bit variants:
    - mistralai/Mistral-7B-Instruct-v0.3 → mlx-community/.../4bit
    - google/gemma-2-2b-it → mlx-community/.../4bit
    - etc.

Example:
    Load and generate with MLX engine::

        from src.engines.mlx_engine import MLX_Engine

        # Load model
        model, tokenizer = MLX_Engine.get_model_and_tokenizer(
            llm_id="mistral-7b",
            llm_local_path="/path/to/mlx/model"
        )

        # Stream generation
        prompt = [{"role": "user", "content": "Hello!"}]
        for token in MLX_Engine.generate_stream(
            model, tokenizer, prompt,
            max_tokens=512, temperature=0.7
        ):
            print(token, end="", flush=True)

Note:
    - Requires mlx_lm library (installed on Mac Silicon only)
    - Models are 4-bit quantized for 4x memory savings
    - Thread-safe via cls._lock for concurrent requests
    - Automatic cleanup after 5 minutes idle time

Warning:
    Only use on Apple Silicon. On other platforms, BaseEngine.get_engine()
    will select CUDA_Engine or CPU_Engine instead.
"""

import os, shutil, logging, importlib
from datetime import datetime
from typing import Optional, Tuple, Any, Generator, Union
from src.engines.base_engine import BaseEngine
from src.core.exceptions import (
    QuantizationException,
    ModelLoadingException,
    GenerationException,
    TokenizationException,
    InsufficientMemoryException,
    FileSystemException,
)
from pathlib import Path

class MLX_Engine(BaseEngine):
    """Singleton Engine for MLX models and tokenizers runtimes.
    Built for Apple Silicon Backends.
    """
    # Mapping of original model links to MLX-quantized versions (same as in llm_downloader.py)
    MODEL_MAPPING : dict = {
        "mistralai/Mistral-7B-Instruct-v0.3": "mlx-community/Mistral-7B-Instruct-v0.3-4bit",
        "mistralai/Mistral-7B-v0.3": "mlx-community/Mistral-7B-v0.3-4bit",
        "google/gemma-2-2b-it": "mlx-community/gemma-2-2b-it-4bit",
        "google/gemma-3-4b-it": "mlx-community/gemma-3-4b-it-4bit",
        "mistralai/Ministral-8B-Instruct-2410": "mlx-community/Ministral-8B-Instruct-2410-4bit",
        "google/gemma-3-12b-it": "mlx-community/gemma-3-12b-it-4bit",
        "mistralai/Mistral-Nemo-Instruct-2407": "mlx-community/Mistral-Nemo-Instruct-2407-4bit"
    }

    @classmethod
    def quant_and_save_from_hf_format(
        cls,
        local_hf_path: Union[str, Path],
        local_dest_path: Union[str, Path],
        quantize: bool = True,
        q_bits: str = "4",
    ) -> None:
        """Convert HuggingFace model to MLX 4-bit quantized format.

        Args:
            local_hf_path: Path to HuggingFace model directory (SafeTensors format).
            local_dest_path: Destination path for quantized MLX model.
            quantize: Whether to apply quantization. Defaults to True.
            q_bits: Quantization bits ("4" for 4-bit). Defaults to "4".

        Returns:
            None. Quantized model saved to local_dest_path.

        Raises:
            Exception: If mlx_lm.convert() fails (corrupted weights, OOM, etc.).

        Note:
            Uses mlx_lm.convert() which removes existing destination directory.
            4-bit quantization reduces model size by ~75% with minimal quality loss.
        """
        """Convert Hugging Face model to MLX format."""

        mlx_lm = importlib.import_module("mlx_lm")

        try:
            logging.info(f"Starting conversion from HF to MLX")
            start = datetime.now()
            if os.path.exists(local_dest_path):
                shutil.rmtree(local_dest_path, ignore_errors=True)
            mlx_lm.convert(
                local_hf_path,
                mlx_path=local_dest_path,
                quantize=quantize,
                q_bits=q_bits
            )
            logging.info(f"Model converted to mlx in {datetime.now() - start}")
        except FileNotFoundError as e:
            raise FileSystemException(
                f"HF model not found at {local_hf_path}",
                trace=str(e)
            )
        except OSError as e:
            if "disk" in str(e).lower() or "space" in str(e).lower():
                raise FileSystemException(
                    f"Disk space issue during quantization: {e}",
                    trace=str(e)
                )
            raise FileSystemException(
                f"Filesystem error during quantization: {e}",
                trace=str(e)
            )
        except MemoryError as e:
            raise InsufficientMemoryException(
                "model quantization",
                trace=str(e)
            )
        except Exception as e:
            raise QuantizationException(
                f"MLX quantization failed: {e}",
                trace=str(e)
            ) 

    @classmethod
    def generate_stream(
        cls,
        model: Any,
        tokenizer: Any,
        prompt: list[dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.1,
        top_p: float = 0.5,
        top_k: int = 64,
        repetition_penalty: Optional[float] = None,
        repetition_context_size: Optional[int] = 1024,
        min_p: float = 0.0,
    ) -> Generator[str, None, None]:
        """Generate streaming response from the model.
        
        Args:
            model: The loaded MLX model.
            tokenizer: The tokenizer associated with the model.
            prompt: List of dictionaries with 'role' and 'content' keys
            max_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling probability threshold
            top_k: Top-k sampling threshold
            repetition_penalty: Penalty for repeating tokens
            repetition_context_size: Number of past tokens to consider for repetition
            min_p: Minimum probability for nucleus sampling
            
        Yields:
            Generated text tokens
        
        Raises:
            Exception: If model loading or generation fails
        """

        mlx_lm = importlib.import_module("mlx_lm")

        with cls._lock:
            try:
                # Tokenize prompt
                prompt_tokens = tokenizer.apply_chat_template(prompt, add_generation_prompt=True)
            except Exception as e:
                raise TokenizationException(
                    f"Failed to apply chat template: {e}",
                    trace=str(e)
                )
            
            try:
                # Create sampler
                sampler = mlx_lm.sample_utils.make_sampler(
                    temperature,
                    top_p,
                    min_p=min_p,
                    top_k=top_k,
                )
                # Build logits processors
                logits_processors = mlx_lm.sample_utils.make_logits_processors(
                repetition_penalty=repetition_penalty,
                repetition_context_size=repetition_context_size,
            )

                # Generate stream
                text = ""
                logging.info("=" * 10)
                for response in mlx_lm.stream_generate(
                    model,
                    tokenizer,
                    prompt_tokens,
                    max_tokens=max_tokens,
                    sampler=sampler,
                    logits_processors=logits_processors if logits_processors != [] else None,
                    prompt_cache=None
                ):  
                    if response:
                        token_repr = response.text.replace('\n', '\\n').replace('\t', '\\t')
                        logging.info(f"Yielding token: {token_repr}")
                        text += response.text
                        yield response.text

                logging.info("=" * 10)

                if len(text) == 0:
                    logging.info("No text generated for this prompt")
                
                logging.info(f"Generation: {response.generation_tokens} tokens")
                logging.info(f"{response.generation_tps:.3f} tokens-per-sec")
                logging.info(f"Peak memory: {response.peak_memory:.3f} GB")

                cls._last_used = datetime.now()  # Update last use time
            except MemoryError as e:
                raise InsufficientMemoryException(
                    "text generation",
                    trace=str(e)
                )
            except Exception as e:
                logging.exception("Generation failed")
                raise GenerationException(
                    f"MLX generation failed: {e}",
                    trace=str(e)
                )
    
    @classmethod
    def get_model_and_tokenizer(
        cls,
        llm_id: str,
        llm_local_path: Union[str, Path],
    ) -> Tuple[Any, Any]:
        """Get or load a model and its tokenizer.
        
        Args:
            llm_id: The LLM model id to load.
            llm_local_dir: The local path to the llm model and tokenizer weights.

            
        Returns:
            Tuple of (model, tokenizer).
            
        Thread-safe and ensures only one copy of the model exists.
        """

        with cls._lock:
            if cls._should_reload_model(llm_id=llm_id):
                return cls._return_cached_model_and_tokenizer()
            
            # Need to load new model
            logging.info(f"Loading new model {llm_id}, cleaning up old model ({cls._model_id}) if exists")
            cls.cleanup()  # Clean old model if exists
            cls._load_model(llm_id=llm_id, llm_local_path=llm_local_path)
            cls._last_used = datetime.now()
            return cls._model, cls._tokenizer
    
    @classmethod
    def _load_model(
        cls,
        llm_id: str,
        llm_local_path: Union[str, Path],
    ) -> None:
        """Internal method to load MLX model and tokenizer into memory.

        Args:
            llm_id: Model identifier for caching (e.g., "mistral-7b").
            llm_local_path: Path to quantized MLX model directory.

        Returns:
            None. Sets cls._model, cls._tokenizer, cls._model_id.

        Raises:
            Exception: If mlx_lm.load() fails (missing weights, incompatible format).

        Note:
            Clears cached model state on failure to prevent inconsistencies.
        """
        """Internal method to load a model and its tokenizer.
        
        Args:
            llm: The LLM model to load.
        """

        mlx_lm = importlib.import_module("mlx_lm")

        logging.info(f"Loading MLX model and tokenizer for {llm_id}...")
        start = datetime.now()
        try:
            cls._model, cls._tokenizer = mlx_lm.load(llm_local_path)
            cls._model_id = llm_id
            logging.info(f"Model and tokenizer loaded in {datetime.now() - start}")
        except FileNotFoundError as e:
            cls._model = None
            cls._tokenizer = None
            cls._model_id = None
            raise FileSystemException(
                f"Model not found at {llm_local_path}",
                trace=str(e)
            )
        except MemoryError as e:
            cls._model = None
            cls._tokenizer = None
            cls._model_id = None
            raise InsufficientMemoryException(
                "model loading",
                trace=str(e)
            )
        except Exception as e:
            cls._model = None
            cls._tokenizer = None
            cls._model_id = None
            logging.error(f"Failed to load model: {e}")
            raise ModelLoadingException(
                f"Failed to load MLX model: {e}",
                trace=str(e)
            )