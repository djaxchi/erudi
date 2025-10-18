import os, shutil, logging, importlib
from datetime import datetime
from typing import Optional, Tuple, Any, Generator, Union
from src.engines.base_engine import BaseEngine
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
        except:
            raise 

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
            except Exception as e:
                logging.exception("Generation failed")
                raise Exception(f"Generation error: {str(e)}")
    
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
        except Exception as e:
            cls._model = None
            cls._tokenizer = None
            cls._model_id = None
            logging.error(f"Failed to load model: {e}")
            raise