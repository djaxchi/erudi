import os
import shutil
import gc
from datetime import datetime
from typing import Optional, Callable

import torch
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
)
from huggingface_hub import snapshot_download

# your HF token…
HF_TOKEN = "***HF_TOKEN_REMOVED***"


def download_llm(
    model_link: str,
    model_id: int,
    save_dir: str = "./data/models",
    cache_dir: str = "./data/models_cache",
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> str:
    """
    1) Downloads every file from Hugging Face to a snapshot folder,
       calling progress_callback(downloaded_bytes, total_bytes)
       as data flows in.
    2) Loads & quantizes the model locally.
    3) Saves tokenizer+model under save_dir/<model_id>.
    """

    # ── PREP ─────────────────────────────────────────────────────────────
    os.makedirs(cache_dir, exist_ok=True)
    os.makedirs(save_dir, exist_ok=True)
    snapshot_dir = os.path.join(cache_dir, f"{model_id}_snapshot")
    shutil.rmtree(snapshot_dir, ignore_errors=True)

    # ── 1) SNAPSHOT DOWNLOAD ─────────────────────────────────────────────
    #    this is where HF does the HTTP GETs; it accepts our callback
    local_folder = snapshot_download(
        repo_id=model_link,
        cache_dir=cache_dir,
        local_dir=snapshot_dir,
        local_dir_use_symlinks=False,  # ensures we get a fresh copy
        use_auth_token=HF_TOKEN,
        progress_callback=progress_callback,  # <──── your hook
    )

    # ── 2) LOAD & QUANTIZE ───────────────────────────────────────────────
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=False,
    )

    # tokenizer & model will read from local_folder (no more network)
    tokenizer = AutoTokenizer.from_pretrained(local_folder, use_auth_token=HF_TOKEN)
    model = AutoModelForCausalLM.from_pretrained(
        local_folder,
        use_auth_token=HF_TOKEN,
        quantization_config=bnb,
        torch_dtype=torch.float16,
        device_map="auto",
    )

    # ── 3) SAVE TO FINAL DIRECTORY ───────────────────────────────────────
    out_dir = os.path.join(save_dir, str(model_id))
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir, exist_ok=True)

    tokenizer.save_pretrained(out_dir)
    model.save_pretrained(out_dir)

    # ── CLEAN UP ────────────────────────────────────────────────────────
    del model, tokenizer
    gc.collect()
    torch.cuda.empty_cache()
    return out_dir
