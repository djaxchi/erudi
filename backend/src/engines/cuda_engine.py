# backend/app/engines/awq_transformers_engine.py






# PAS DU TOUT BON POUR L'INSTANT, JUSTE UNE BASE




"""
AWQ + Transformers engine implementation.

Provides a class-level singleton-style engine that:
- can quantize a HuggingFace model folder into an AWQ-ready folder (quant_and_save_from_hf_format)
- can load a model + tokenizer from a local HF-format folder (_load_model_and_tokenizer)
- exposes get_model_and_tokenizer to ensure a model is loaded and returned
- exposes generate_stream as a synchronous generator yielding string chunks
- exposes cleanup and an idle cleanup monitor (start/stop task)

Design constraints & choices:
- All heavy imports (transformers, torch, auto_awq CLI or lib) are lazy and only happen inside functions.
- The code is OS-agnostic: if a Python API for AWQ is not available we try to call a CLI via subprocess.
- Thread-safety via a class-level lock around load/cleanup operations.
- Singleton-ish: the class holds class attributes `_instance`, `_tokenizer`, `_model_id`.
- Streaming generation uses transformers.TextIteratorStreamer executed in a background thread and read synchronously.
"""
import threading, asyncio, json, gc
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, Tuple, Generator, List
from src.engines.base_engine import BaseEngine
from src.core.logging import logger

"""
# Environment tuning for deterministic behavior (caller may already set these)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
"""
class CUDA_Engine(BaseEngine):
    """
    Engine implementing AWQ quantization + Transformers runtime for CUDA-capable machines.

    Class methods and state are used so the engine behaves like a controlled global singleton.
    """

    _instance: Optional[Any] = None
    _tokenizer: Optional[Any] = None
    _model_id: Optional[str] = None
    _last_used: Optional[datetime] = None
    _lock = threading.Lock()
    _cleanup_task = None
    _max_idle_time = 300  # 5 minutes

    _device: Optional[str] = None

    # ----------------------
    # Quantization & packaging
    # ----------------------
    @classmethod
    def quant_and_save_from_hf_format(
        cls,
        local_hf_dir: str,
        dest_dir: str,
        quantize: bool = True,
        q_bit: str = "4",
    ) -> None:
        """
        Convert a HuggingFace model (already downloaded to local_hf_dir) into a directory
        ready for inference with AWQ quantization. If quantize is False, simply copy the HF
        files to dest_dir (maybe stripping large files if needed).

        Strategy:
        - Try to use a Python API (autoawq / awq) if available.
        - Fallback to invoking a CLI (`auto-awq` or `awq`) via subprocess.
        - Guarantee dest_dir exists and contains tokenizer files + model files in a format
          that Transformers can load (safetensors or pytorch bin + config + tokenizer).
        - Write a small metadata file `awq_meta.json` to indicate quantization parameters.
        """
        src = Path(local_hf_dir)
        dst = Path(dest_dir)
        if not src.exists():
            raise FileNotFoundError(f"Source HF dir not found: {src}")

        dst.mkdir(parents=True, exist_ok=True)

        # If quantize is False: simple copy (overwrite)
        if not quantize:
            # Copy all relevant files (config, tokenizer, model files). Use copytree semantics.
            logger.info("quantize=False: copying HF directory to dest")
            # Copy file-by-file to allow partial overlays
            for p in src.iterdir():
                targ = dst / p.name
                if p.is_dir():
                    if targ.exists():
                        shutil.rmtree(targ)
                    shutil.copytree(p, targ)
                else:
                    shutil.copy2(p, targ)
            # metadata
            meta = {"quantized": False, "source": str(src), "q_bit": None, "created_at": datetime.utcnow().isoformat()}
            (dst / "awq_meta.json").write_text(json.dumps(meta))
            return
        
        

    # ----------------------
    # Model loading
    # ----------------------
    @classmethod
    def _load_model_and_tokenizer(cls, llm_id: str, llm_link: str) -> None:
        """
        Internal loader: loads tokenizer + transformers model into class attributes.

        - llm_link is expected to be a local directory path (HF snapshot) or a HF id.
        - We try to load with transformers in float16 and device_map='auto' to let accelerate handle placement.
        - We handle absence of torch/transformers with informative errors.
        """
        with cls._lock:
            logger.info("Loading model/tokenizer for id=%s link=%s", llm_id, llm_link)
            try:
                from transformers import AutoTokenizer, AutoModelForCausalLM
            except Exception as e:
                logger.exception("transformers import failed: %s", e)
                raise RuntimeError("transformers is required for AWQTransformerEngine") from e

            # Determine path: prefer local folder if it exists
            model_path = Path(llm_link)
            if model_path.exists():
                load_source = str(model_path)
            else:
                load_source = llm_link  # may be HF repo id; transformers will handle caching

            # Attempt to load tokenizer first (fast)
            try:
                tokenizer = AutoTokenizer.from_pretrained(load_source, use_fast=True)
            except Exception as e:
                logger.exception("Tokenizer load failed for %s: %s", load_source, e)
                raise

            # Load model: prefer safe dtype (float16) if possible
            try:
                import torch
                torch_available = True
            except Exception:
                torch_available = False

            load_kwargs = {}
            if torch_available:
                # try to load into auto device_map to exploit GPU if present
                # prefer float16 for GPU; fallback to cpu if no GPU
                try:
                    from accelerate import init_empty_weights  # not required, only check presence
                    pass
                except Exception:
                    pass
                # Use device_map 'auto' and let accelerate choose
                load_kwargs["device_map"] = "auto"
                load_kwargs["torch_dtype"] = getattr(__import__("torch"), "float16")
            else:
                # CPU fallback: let transformers load on CPU
                load_kwargs["device_map"] = None

            # Try to load the model
            try:
                model = AutoModelForCausalLM.from_pretrained(load_source, **load_kwargs)
            except Exception as e:
                logger.exception("Model loading failed for %s: %s", load_source, e)
                # try a safer CPU-only load
                try:
                    model = AutoModelForCausalLM.from_pretrained(load_source, device_map=None)
                except Exception as e2:
                    logger.exception("Fallback CPU model load failed: %s", e2)
                    raise

            # Persist to class attrs
            cls._instance = model
            cls._tokenizer = tokenizer
            cls._model_id = llm_id
            cls._last_used = datetime.utcnow()
            # record device info for metadata
            try:
                import torch
                cls._device = str(next(iter(set(p.device for p in model.parameters() if hasattr(p, "device"))), "cpu"))
            except Exception:
                cls._device = "unknown"

            logger.info("Loaded model %s (id=%s)", load_source, llm_id)

    @classmethod
    def get_model_and_tokenizer(cls, llm_id: str, llm_link: str) -> Tuple[Any, Any]:
        """
        Ensure the requested model (by id) is loaded and return (model, tokenizer).
        If a different model is loaded, it will cleanup and load the requested one.
        """
        with cls._lock:
            if cls._model_id == llm_id and cls._instance is not None and cls._tokenizer is not None:
                cls._last_used = datetime.utcnow()
                logger.debug("Reusing cached model %s", llm_id)
                return cls._instance, cls._tokenizer

            # Need to load new model
            logger.info("Switching to model %s (link=%s)", llm_id, llm_link)
            try:
                # Clean previous model if present
                if cls._instance is not None:
                    try:
                        cls.cleanup()
                    except Exception:
                        logger.exception("cleanup of previous model failed")

                cls._load_model_and_tokenizer(llm_id, llm_link)
                return cls._instance, cls._tokenizer
            except Exception as e:
                logger.exception("Failed to load model %s: %s", llm_id, e)
                raise

    # ----------------------
    # Generation
    # ----------------------
    @classmethod
    def generate_stream(
        cls,
        model: Any,
        tokenizer: Any,
        prompt: List[dict],
        max_tokens: int = 1024,
        temperature: float = 1.0,
        top_p: float = 0.95,
        repetition_penalty: Optional[float] = None,
        *args
    ) -> Generator[str, None, None]:
        """
        Synchronous generator that yields text chunks produced by Transformers + AWQ quantized model.

        Implementation:
        - Build prompt string from `prompt` list[dict{'role','content'}]
        - Use transformers.TextIteratorStreamer to stream tokens
        - Run model.generate(...) in a background thread which feeds the streamer
        - Yield chunks as they arrive from the streamer
        """
        if model is None or tokenizer is None:
            raise RuntimeError("model and tokenizer must be provided to generate_stream")

        # Prepare textual prompt — caller may provide a list of role/content dicts
        # Simple canonicalization: join messages with newline markers (customize via inference_utils in app)
        try:
            # Prefer to use tokenizer.chat or an external helper if available; fallback simple join
            if isinstance(prompt, (list, tuple)):
                prompt_text = "\n".join(f"{m.get('role','user')}: {m.get('content','')}" for m in prompt)
            else:
                prompt_text = str(prompt)
        except Exception:
            prompt_text = str(prompt)

        logger.debug("Starting streaming generation (tokens=%s, temp=%s, top_p=%s)", max_tokens, temperature, top_p)

        # Lazy import transformers streaming tools
        try:
            from transformers import TextIteratorStreamer
        except Exception as e:
            logger.exception("transformers TextIteratorStreamer import failed: %s", e)
            # Fallback: run non-streaming generate and yield whole text
            try:
                out = cls._sync_generate_full_text(model, tokenizer, prompt_text, max_tokens=max_tokens, temperature=temperature, top_p=top_p, *args)
                yield out
                return
            except Exception as exc:
                raise RuntimeError(f"Generation failed and streaming unavailable: {exc}") from exc

        streamer = TextIteratorStreamer(tokenizer, timeout=10.0, skip_prompt=True)

        # Prepare inputs and generation kwargs
        gen_kwargs = dict(
            input_ids=None,
            max_new_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            do_sample=True,
            streamer=streamer,
        )

        # Tokenize prompt to tensors lazily and push to device of model
        try:
            inputs = tokenizer(prompt_text, return_tensors="pt")
            # Move tensors to model device if possible
            try:
                import torch
                device = next(model.parameters()).device
                inputs = {k: v.to(device) for k, v in inputs.items()}
            except Exception:
                pass
            gen_kwargs.update(inputs)
        except Exception:
            # Fallback: let generate handle raw prompt via tokenizer in the generation thread
            gen_kwargs.pop("input_ids", None)

        # Start generation in a background thread (model.generate will call streamer)
        def _generate_thread():
            try:
                # Some models require passing 'inputs' as kwargs; others accept prompt via tokenizer
                model.generate(**gen_kwargs)
            except Exception as e:
                logger.exception("Model generation thread failed: %s", e)
                # propagate by feeding an exception marker in streamer? Here just log.

        gen_thread = threading.Thread(target=_generate_thread, daemon=True)
        gen_thread.start()

        # Iterate streamer in current thread (TextIteratorStreamer is iterable)
        try:
            for chunk in streamer:
                # streamer yields strings or pieces of text
                if not isinstance(chunk, str):
                    chunk = str(chunk)
                cls._last_used = datetime.utcnow()
                yield chunk
        finally:
            # Ensure background thread is joined (best-effort)
            try:
                gen_thread.join(timeout=0.1)
            except Exception:
                pass

    @classmethod
    def _sync_generate_full_text(cls, model: Any, tokenizer: Any, prompt_text: str, **gen_opts) -> str:
        """
        Fallback sync generation that returns full text (non-streaming).
        """
        try:
            inputs = tokenizer(prompt_text, return_tensors="pt")
            try:
                import torch
                device = next(model.parameters()).device
                inputs = {k: v.to(device) for k, v in inputs.items()}
            except Exception:
                pass
            out_ids = model.generate(**inputs, **gen_opts)
            # out_ids may be a tensor; decode first sequence
            text = tokenizer.decode(out_ids[0], skip_special_tokens=True)
            cls._last_used = datetime.utcnow()
            return text
        except Exception as e:
            logger.exception("Synchronous generation failed: %s", e)
            raise

    # ----------------------
    # Cleanup & monitoring
    # ----------------------
    @classmethod
    def cleanup(cls) -> None:
        """
        Free model and tokenizer from memory and attempt to release GPU/MPS resources.
        """
        with cls._lock:
            logger.info("Cleaning up AWQTransformerEngine model (id=%s)", cls._model_id)
            cls._instance = None
            cls._tokenizer = None
            cls._model_id = None
            cls._last_used = None
            cls._device = None
            # GPU / MPS caches
            try:
                import torch
                if hasattr(torch, "cuda") and torch.cuda.is_available():
                    try:
                        torch.cuda.empty_cache()
                    except Exception:
                        logger.exception("torch.cuda.empty_cache failed")
                if hasattr(torch.backends, "mps") and getattr(torch.backends, "mps").is_available():
                    try:
                        torch.mps.empty_cache()
                    except Exception:
                        logger.exception("torch.mps.empty_cache failed")
            except Exception:
                # torch not available; ignore
                pass
            try:
                gc.collect()
            except Exception:
                pass

    @classmethod
    def _should_cleanup(cls) -> bool:
        """
        Determine whether model should be cleaned up based on idle time.
        """
        logger.debug("Checking whether cleanup is needed")
        if cls._last_used is None or cls._instance is None:
            return False
        idle = datetime.utcnow() - cls._last_used
        return idle > timedelta(seconds=cls._max_idle_time)

    @classmethod
    async def _cleanup_monitor(cls) -> None:
        """
        Async background coroutine to periodically check and cleanup idle models.
        """
        logger.info("AWQTransformerEngine cleanup monitor started")
        try:
            while True:
                await asyncio.sleep(max(1, int(cls._max_idle_time // 2)))
                with cls._lock:
                    if cls._should_cleanup():
                        logger.info("Idle timeout reached: cleaning up model")
                        try:
                            cls.cleanup()
                        except Exception:
                            logger.exception("Error during scheduled cleanup")
        except asyncio.CancelledError:
            logger.info("AWQTransformerEngine cleanup monitor cancelled")
        except Exception:
            logger.exception("AWQTransformerEngine cleanup monitor crashed")

    @classmethod
    def start_cleanup_task(cls) -> None:
        """
        Start the cleanup monitor if not already running. This will create an asyncio Task
        in the current event loop when possible. If no running loop is available, spawn a
        dedicated thread that runs an event loop for the monitor (best-effort).
        """
        if cls._cleanup_task is not None:
            logger.debug("Cleanup task already running")
            return

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                cls._cleanup_task = loop.create_task(cls._cleanup_monitor())
                logger.info("Started AWQ cleanup monitor in existing event loop")
                return
        except RuntimeError:
            # no event loop in this thread
            pass

        # Spawn a dedicated thread running its own loop
        def _thread_target():
            try:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                cls._cleanup_task = new_loop.create_task(cls._cleanup_monitor())
                new_loop.run_until_complete(cls._cleanup_task)
            except Exception:
                logger.exception("Cleanup monitor thread crashed")

        t = threading.Thread(target=_thread_target, daemon=True)
        t.start()
        logger.info("Started AWQ cleanup monitor in background thread")

    @classmethod
    def stop_cleanup_task(cls) -> None:
        """
        Cancel and clear the cleanup task if present.
        """
        if cls._cleanup_task is None:
            logger.debug("No cleanup task to stop")
            return

        try:
            # If it's an asyncio.Task in the running loop, cancel it
            if hasattr(cls._cleanup_task, "cancel"):
                cls._cleanup_task.cancel()
                logger.info("Cancelled cleanup asyncio task")
            else:
                logger.info("Cleanup task not a coroutine task; best-effort stop")
        except Exception:
            logger.exception("Failed to cancel cleanup task")
        finally:
            cls._cleanup_task = None
