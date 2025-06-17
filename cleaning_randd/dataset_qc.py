#!/usr/bin/env python3
import builtins

# ── Monkey-patch builtins.open once to default to UTF-8 for text/JSON reads ──────
_orig_open = builtins.open


def _utf8_open(
    file,
    mode="r",
    buffering=-1,
    encoding=None,
    errors=None,
    newline=None,
    closefd=True,
    opener=None,
):
    if "b" not in mode and encoding is None:
        encoding = "utf-8"
    return _orig_open(file, mode, buffering, encoding, errors, newline, closefd, opener)


builtins.open = _utf8_open

import os, glob, argparse, re, hashlib
from typing import List
from statistics import mean
from pathlib import Path

from mistral_common.tokens.tokenizers.tekken import Tekkenizer
from mistral_common.tokens.tokenizers.mistral import MistralTokenizer

'''from transformers import AutoTokenizer, AutoModelForCausalLM
import random
from typing import List, Tuple, Dict
import torch

def compute_perplexities(
    model_path: str,
    docs: List[str],
    sample_max_tokens: int = 2048,
    top_k: int = 3,
    device: str = "cpu"
) -> Dict[str, object]:
    """
    Loads a Mistral-7B model from `model_path` and computes
    a perplexity score for each document based on a sample
    of up to `sample_max_tokens` tokens from the start.
    
    Returns a dict with:
      - mean_perplexity: float
      - doc_perplexities: List[float]  # same length as docs
      - lowest_perplexity_docs: List[Tuple[int, float]]
          # (doc_index, perplexity) for the top_k easiest docs
    """
    # load tokenizer & model
    tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        device_map="auto" if device != "cpu" else None,
        torch_dtype=torch.float16 if device != "cpu" else torch.float32,
        load_in_4bit=True if device != "cpu" else False
    )
    model.to(device)
    model.eval()

    perp_scores: List[float] = []
    for text in docs:
        # tokenize & truncate to sample_max_tokens
        inputs = tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=sample_max_tokens
        ).to(model.device)

        with torch.no_grad():
            loss = model(**inputs, labels=inputs.input_ids).loss

        perp = math.exp(loss.item())
        perp_scores.append(perp)

    mean_perp = sum(perp_scores) / len(perp_scores)

    # pick the top_k lowest‐perplexity docs
    lowest = sorted(enumerate(perp_scores), key=lambda x: x[1])[:top_k]

    return {
        "mean_perplexity": mean_perp,
        "doc_perplexities": perp_scores,
        "lowest_perplexity_docs": lowest
    }
'''


# 1) Load text files into a list of strings
def load_texts(path: str) -> List[str]:
    if os.path.isdir(path):
        files = glob.glob(os.path.join(path, "**", "*.txt"), recursive=True)
    else:
        files = [path]
    docs = []
    for fp in files:
        try:
            with open(fp) as f:
                docs.append(f.read())
        except Exception:
            with open(fp, "r", errors="replace") as f:
                docs.append(f.read())
    return docs


# 2) Optional cleaning steps
def remove_punctuation(text: str) -> str:
    return re.sub(r"[^\w\s]+", "", text)


_STOP_WORDS = {
    "a",
    "an",
    "and",
    "the",
    "in",
    "on",
    "of",
    "for",
    "to",
    "is",
    "are",
    "it",
    "this",
}


def remove_stopwords(text: str) -> str:
    """
    Remove stop-words but preserve *all* whitespace (spaces, tabs, newlines).
    We split on any run of whitespace, keep the separators, then filter only the word-tokens.
    """
    # This regex will split into runs of non-whitespace (\S+) *or* runs of whitespace (\s+),
    # preserving both in the returned list.
    parts = re.findall(r"\S+|\s+", text)
    out_parts = []
    for p in parts:
        # If it’s purely whitespace, keep it verbatim
        if p.isspace():
            out_parts.append(p)
        else:
            # Otherwise it’s a token: drop it if it’s a stop-word
            if p.lower() not in _STOP_WORDS:
                out_parts.append(p)
    return "".join(out_parts)


def lowercase(text: str) -> str:
    return text.lower()


# 3a) Cross-document duplication
def duplication_ratio(docs: List[str]) -> float:
    hashes = [hashlib.sha256(d.encode("utf-8")).hexdigest() for d in docs]
    return (len(hashes) - len(set(hashes))) / len(hashes)


# 3b) In-document duplication
def in_doc_duplication_ratio(docs: List[str]) -> float:
    """
    For each document, split on blank lines into paragraphs,
    then compute the fraction of paragraphs that are exact duplicates.
    Finally, return the average duplication ratio across all docs.
    """
    ratios = []
    for doc in docs:
        # split on 2+ newlines (blank‐line paragraphs)
        paras = [p.strip() for p in re.split(r"\n\s*\n", doc) if p.strip()]
        if len(paras) <= 1:
            ratios.append(0.0)
            continue
        # hash each paragraph
        para_hashes = [hashlib.sha256(p.encode("utf-8")).hexdigest() for p in paras]
        dup_count = len(para_hashes) - len(set(para_hashes))
        ratios.append(dup_count / len(para_hashes))
    return mean(ratios)


# 3c) Length stats
def length_stats(docs: List[str], tekkenizer: Tekkenizer, max_len: int):
    lengths = [len(tekkenizer.encode(d, bos=False, eos=False)) for d in docs]
    return {
        "total_tokens": sum(lengths),
        "mean_tokens": mean(lengths),
        "pct_over_max": sum(l > max_len for l in lengths) / len(lengths),
    }


# 3d) Aggregate QC metrics
def evaluate(docs: List[str], tekkenizer: Tekkenizer, max_len: int):
    return {
        "docs": len(docs),
        "dup_ratio": duplication_ratio(docs),
        "in_doc_dup": in_doc_duplication_ratio(docs),
        **length_stats(docs, tekkenizer, max_len),
    }


# 4) Pretty-print before/after
def print_comparison(orig, clean, max_len: int):
    print(f"\nMetric                    Before      After")
    print(f"─────                     ────────    ────────")
    print(f"Documents                 {orig['docs']:>8}    {clean['docs']:>8}")
    print(
        f"Duplication ratio         {orig['dup_ratio']:>8.2%}    {clean['dup_ratio']:>8.2%}"
    )
    print(
        f"In-doc duplication ratio  {orig['in_doc_dup']:>8.2%}    {clean['in_doc_dup']:>8.2%}"
    )
    print(
        f"Total tokens              {orig['total_tokens']:>8}    {clean['total_tokens']:>8}"
    )
    print(
        f"Mean tokens per doc       {orig['mean_tokens']:>8.1f}    {clean['mean_tokens']:>8.1f}"
    )
    print(
        f"% over {max_len} tokens      {orig['pct_over_max']:>8.2%}    {clean['pct_over_max']:>8.2%}"
    )


# 5) Main orchestration
def main():
    parser = argparse.ArgumentParser(
        description="Corpus QC for Mistral-7B: cleaning, length & duplication metrics"
    )
    parser.add_argument(
        "--input",
        default="cleaning_randd/dataset",
        help="Path to .txt file or directory of .txt files",
    )
    parser.add_argument(
        "--max_len",
        type=int,
        default=8192,
        help="Context window size of Mistral-7B (default: 8192)",
    )
    args = parser.parse_args()

    docs = load_texts(args.input)
    if not docs:
        print(f"❌ No .txt files found at {args.input}")
        return

    # Load Mistral’s Tekken BPE v3
    data_path = MistralTokenizer._data_path()
    tek_file = Path(data_path) / "tekken_240718.json"
    tekkenizer = Tekkenizer.from_file(str(tek_file))

    # Evaluate before any cleaning
    orig_metrics = evaluate(docs, tekkenizer, args.max_len)

    # Interactive cleaning
    cleaned = docs
    if input("Remove punctuation? [y/N] ").strip().lower().startswith("y"):
        cleaned = [remove_punctuation(d) for d in cleaned]
    if input("Remove stop-words? [y/N] ").strip().lower().startswith("y"):
        cleaned = [remove_stopwords(d) for d in cleaned]
    if input("Lowercase text?    [y/N] ").strip().lower().startswith("y"):
        cleaned = [lowercase(d) for d in cleaned]

    # Evaluate after cleaning
    clean_metrics = evaluate(cleaned, tekkenizer, args.max_len)

    # Print side-by-side comparison
    print_comparison(orig_metrics, clean_metrics, args.max_len)


if __name__ == "__main__":
    main()
