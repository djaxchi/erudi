#!/usr/bin/env python3
import os
import glob
import argparse
import re
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from typing import List
from transformers import GPT2LMHeadModel, GPT2TokenizerFast
import torch
import math



# — Only needs these NLTK models once:
nltk.download('punkt_tab', quiet=True)
nltk.download("punkt", quiet=True)
nltk.download("stopwords", quiet=True)
nltk.download("wordnet", quiet=True)


# 1. Load .txt file(s)
def load_texts(path: str) -> List[str]:
    if os.path.isdir(path):
        files = glob.glob(os.path.join(path, "**", "*.txt"), recursive=True)
    else:
        files = [path]
    docs = []
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                docs.append(f.read())
        except UnicodeDecodeError:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                docs.append(f.read())
    return docs


# 2. Cleanup helpers
def remove_punctuation(text: str) -> str:
    return re.sub(r"[^\w\s]+", "", text)


def remove_urls(text: str) -> str:
    return re.sub(r"http\S+|www\.\S+", "", text)


_stop_words = set(stopwords.words("english"))


def remove_stopwords(tokens: List[str]) -> List[str]:
    return [t for t in tokens if t.lower() not in _stop_words]


def lowercase(text: str) -> str:
    return text.lower()


# 3. Tokenization + Lemmatization
_wnl = WordNetLemmatizer()


def lemmatize_tokens(tokens: List[str]) -> List[str]:
    return [_wnl.lemmatize(t) for t in tokens]


def tokenize_and_lemmatize(text: str) -> List[str]:
    # 1) lowercase
    text = lowercase(text)
    # 2) remove punctuation & URLs
    text = remove_punctuation(remove_urls(text))

    ppl = calculate_perplexity(text)

    # 3) word tokenize
    tokens = word_tokenize(text)
    # 4) drop stop-words
    tokens = remove_stopwords(tokens)
    # 5) lemmatize
    return lemmatize_tokens(tokens), ppl

def calculate_perplexity(text):
    model_name = "gpt2"
    model = GPT2LMHeadModel.from_pretrained(model_name)
    tokenizer = GPT2TokenizerFast.from_pretrained(model_name)
    model.eval()

    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=1024)
    with torch.no_grad():
        outputs = model(**inputs, labels=inputs["input_ids"])
        loss = outputs.loss
    return math.exp(loss.item())




# ——————————————————————————————————————————————————————————
def main():
    

    docs = load_texts("dataset/badText.txt")
    
    for i, doc in enumerate(docs, 1):
        lemmas, ppl = tokenize_and_lemmatize(doc)
        print(f"\nDocument {i}/{len(docs)}: {len(lemmas)} lemmas")
        print("First 20 lemmas:", lemmas[:20])
        print(f"Perplexity: {ppl:.2f}")
        if ppl < 100:
            print("Texte de bonne qualité linguistique.")
        elif ppl < 200:
            print("Texte acceptable mais à vérifier.")
        else:
            print("Texte de mauvaise qualité ou bruit possible.")


if __name__ == "__main__":
    main()
