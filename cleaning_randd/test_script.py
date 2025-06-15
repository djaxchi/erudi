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

# — Only needs these NLTK models once:
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
    # 3) word tokenize
    tokens = word_tokenize(text)
    # 4) drop stop-words
    tokens = remove_stopwords(tokens)
    # 5) lemmatize
    return lemmatize_tokens(tokens)


# ——————————————————————————————————————————————————————————
def main():
    p = argparse.ArgumentParser(description="Load text(s) and output lemmatized tokens")
    p.add_argument("input", help="Path to a .txt file or folder of .txt files")
    args = p.parse_args()

    docs = load_texts(args.input)
    if not docs:
        print("No .txt files found at", args.input)
        return

    for i, doc in enumerate(docs, 1):
        lemmas = tokenize_and_lemmatize(doc)
        print(f"\nDocument {i}/{len(docs)}: {len(lemmas)} lemmas")
        print("First 20 lemmas:", lemmas[:20])


if __name__ == "__main__":
    main()
