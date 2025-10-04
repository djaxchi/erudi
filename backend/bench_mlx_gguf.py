import shutil
import mlx_lm
import llama_cpp
from datetime import datetime
import psutil
import os
import subprocess

hf_dir = "./data/models/833"
mlx_dir = "./data/models/test/"
gguf_dir = "./data/models/gguf-gem1b/"

# ------------------------
# MEMORY LOGGING
# ------------------------
def log_memory(note: str = ""):
    """Print current process memory usage in MB"""
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / 1024**2
    print(f"[Memory] {note} RSS = {mem:.2f} MB")
    return mem

# ------------------------
# MLX MODEL FUNCTIONS
# ------------------------
def model_file_size_gb(mlx_dir: str):
    """Estimate MLX model memory based on .safetensors file size"""
    total_bytes = 0
    for root, _, files in os.walk(mlx_dir):
        for f in files:
            if f.endswith(".safetensors"):
                total_bytes += os.path.getsize(os.path.join(root, f))
    return total_bytes / 1024**3  # GB

def convert_model_hf_mlx():
    print("Converting HF model to MLX format")
    start = datetime.now()
    mlx_lm.convert(
        hf_dir,
        quantize=True,
        q_bits=4,
        mlx_path=mlx_dir
    )
    print(f"Model converted in {datetime.now() - start}")

def load_and_chat_with_mlx(text: str):
    log_memory("Before loading MLX model")

    print("Loading MLX model and tokenizer...")
    start = datetime.now()
    mlx_model, mlx_tok = mlx_lm.load(hf_dir)
    print(f"Model and tokenizer loaded in {datetime.now() - start}")
    log_memory("After loading MLX model")

    # Approx model size on disk
    size_gb = model_file_size_gb(mlx_dir)
    print(f"Approx MLX model size on disk (.safetensors): {size_gb:.2f} GB")

    # Sampler
    temperature = 0.1
    top_p = 0.3
    min_p = 0.0
    top_k = 64
    max_tokens = 3200
    verbose = True
    sampler = mlx_lm.sample_utils.make_sampler(
        temperature,
        top_p,
        min_p=min_p,
        top_k=top_k,
        xtc_special_tokens=mlx_tok.encode("\n") + list(mlx_tok.eos_token_ids)
    )

    # Tokenize prompt
    print("Tokenizing prompt")
    start = datetime.now()
    system_prompt = """You are a helpful and concise conversational assistant."""
    prompt_tokens = mlx_tok.apply_chat_template(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]
    )
    print(f"System Prompt is:\n\n{system_prompt}")
    print(f"Prompt tokenized in {datetime.now() - start} seconds")

    # --- compute prompt length robustly (list or mx.array) ---
    try:
        # prompt_tokens may be list[int] or mx.array
        if hasattr(prompt_tokens, "size"):
            prompt_len = int(prompt_tokens.size)
        else:
            prompt_len = len(prompt_tokens)
    except Exception:
        print("Failed to compute prompt length, defaulting to 0")
        prompt_len = 0

    # get EOS ids (tokenizer may expose eos_token_ids or eos_token_id)
    eos_ids = getattr(mlx_tok, "eos_token_ids", None)
    if eos_ids is None:
        single_eos = getattr(mlx_tok, "eos_token_id", None)
        eos_ids = [single_eos] if single_eos is not None else []

    # --- robust min-new-tokens processor ---
    def min_new_tokens_processor(min_new_tokens: int = 10, prompt_len: int = prompt_len, eos_ids=None, patience: int = 3):
        """
        Forbid EOS until at least `min_new_tokens` have been generated AFTER the prompt.
        If the model is stuck repeating the same token `patience` times, allow EOS to break out.
        """
        if eos_ids is None:
            local_eos_ids = []
        else:
            local_eos_ids = eos_ids

        def processor(tokens, logits):
            # tokens is an mx.array of the full sequence (prompt + generated)
            try:
                tokens_len = int(tokens.size)  # preferred for mx.array
            except Exception:
                try:
                    tokens_len = len(tokens)
                except Exception:
                    print(f"Failed to compute tokens length, got type {type(tokens)}")
                    tokens_len = 0

            generated = tokens_len - prompt_len
            # forbid EOS until we reach the minimum generated tokens
            if generated < min_new_tokens:
                for eid in local_eos_ids:
                    if eid is None:
                        continue
                    # safety: ensure index in vocab range
                    if 0 <= eid < logits.shape[-1]:
                        logits[:, eid] = -1e9 # What does this mean ? Why -1e9 ?

            # simple stuck-detection: if last `patience` tokens are identical, allow EOS to escape
            # (prevents infinite loops where the model just repeats one token)
            if generated >= 1 and generated >= patience:
                try:
                    # tokens.tolist() -> list of ints
                    last = tokens.tolist()[-patience:]
                    if len(last) == patience and all(x == last[0] for x in last):
                        # do nothing -> EOS allowed (we do not re-apply -1e9)
                        pass
                except Exception:
                    # if tolist() fails for some reason, ignore
                    pass

            return logits

        return processor

    # --- Build logits_processors (keep repetition_penalty) and append our min_new_tokens processor ---
    logits_processors = mlx_lm.sample_utils.make_logits_processors(
        repetition_penalty=1.3,
        repetition_context_size=60,
    )

    logits_processors.append(min_new_tokens_processor(min_new_tokens=5, prompt_len=prompt_len, eos_ids=eos_ids, patience=5))


    # Generate response
    print(f"Generating response from MLX model for prompt: {text}")
    start = datetime.now()
    response = mlx_lm.generate(
        mlx_model,
        mlx_tok,
        prompt_tokens,
        max_tokens=max_tokens,
        verbose=verbose,
        sampler=sampler,
        logits_processors=logits_processors,
        prompt_cache=None
    )
    print(f"Response generated in {datetime.now() - start} seconds")
    log_memory("After MLX generation")

# ------------------------
# GGUF / LLaMA.CPP FUNCTIONS
# ------------------------

def convert_model_hf_gguf():
    print("Converting HF to GGUF Format")
    start = datetime.now()
    llama_cpp.convert_hf_to_gguf(
        hf_dir, gguf_dir,
        quantize=True,
        q_bits=4
    )
    print(f"Convertion from HF to GGUF finished in {datetime.now() - start} seconds.")


# ------------------------
# MAIN
# ------------------------
if __name__ == "__main__":
    
    # convert_model_hf_mlx()
    load_and_chat_with_mlx(input("Enter a prompt for MLX model: "))