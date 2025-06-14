import os
import glob
import argparse
import random
import hashlib
from mistral_tokenizer import Tokenizer
import text_dedup.hash as td_hash
import fasttext
from presidio_analyzer import RecognizerRegistry
import textstat
import math
import kenlm

# Scoring parameters
WEIGHTS = {
    'struct': 0.25,
    'dup': 0.20,
    'lang': 0.15,
    'pii': 0.15,
    'noise': 0.10,
    'nov': 0.15
}
TARGETS = {
    'struct': 0.02,
    'dup': 0.05,
    'lang': 0.03,
    'pii': 0.005,
    'noise': 0.05,
    'nov': 0.10
}
PENALTIES = {
    'struct': 50,
    'dup': 40,
    'lang': 50,
    'pii': 60,
    'noise': 30,
    'nov': 40
}

# Utility: clamp

def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(x, hi))

# Subscore and global score

def subscore(value, target, k):
    penalty = k * max(value - target, 0.0)
    return max(0.0, 100.0 - penalty)


def compute_score(metrics):
    subs = {m: subscore(metrics[m], TARGETS[m], PENALTIES[m])
            for m in WEIGHTS}
    global_score = sum(WEIGHTS[m] * subs[m] for m in WEIGHTS)
    return global_score, subs

# Load textual files

def load_texts(path):
    files = glob.glob(os.path.join(path, '**', '*.txt'), recursive=True)
    docs = []
    for f in files:
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                docs.append(fp.read())
        except UnicodeDecodeError:
            with open(f, 'r', encoding='utf-8', errors='replace') as fp:
                docs.append(fp.read())
    return docs

# 1. Structural metrics

def structural_metrics(docs, tokenizer):
    lengths = [len(tokenizer.encode(d).ids) for d in docs]
    over = sum(1 for l in lengths if l > tokenizer.max_length)
    mean = sum(lengths) / len(lengths)
    pct_over = over / len(lengths)
    return {'mean_tokens': mean, 'pct_over_context': pct_over}

# 2. Duplication metrics

def duplication_metrics(docs):
    hashes = td_hash.hash_strings(docs)
    total = len(hashes)
    unique = len(set(hashes))
    dup_ratio = (total - unique) / total
    return {'dup_ratio_exact': dup_ratio}

# 3. Language ID metrics

def language_metrics(docs, lang_model, target_lang='en'):
    off = 0
    for d in docs:
        lang, _ = lang_model.predict(d.replace('\n', ' '), k=1)
        if lang[0] != target_lang:
            off += 1
    pct_off = off / len(docs)
    return {'off_language_pct': pct_off}

# 4. PII & safety metrics

def pii_metrics(docs, analyzer):
    pii_count = 0
    for text in docs:
        results = analyzer.analyze(text=text, entities=[], language='en')
        if results:
            pii_count += 1
    pct_pii = pii_count / len(docs)
    return {'pii_pct': pct_pii}

# 5. Noise / entropy metrics

def shannon_entropy(text):
    if not text:
        return 0
    freq = {}
    for c in text:
        freq[c] = freq.get(c, 0) + 1
    ent = 0.0
    length = len(text)
    for count in freq.values():
        p = count / length
        ent -= p * math.log2(p)
    return ent


def noise_metrics(docs):
    low = 0
    for text in docs:
        ent = shannon_entropy(text)
        if ent < 3 or textstat.flesch_kincaid_grade(text) < 5:
            low += 1
    pct_low = low / len(docs)
    return {'low_entropy_pct': pct_low}

# 6. Novelty / perplexity metrics

def perplexity_metrics(docs, kenlm_model):
    low, high = 0, 0
    ppl_values = []
    for text in docs:
        ppl = kenlm_model.perplexity(text)
        ppl_values.append(ppl)
    median = sorted(ppl_values)[len(ppl_values)//2]
    for ppl in ppl_values:
        if ppl < (median / 2) or ppl > (median * 2):
            high += 1
    pct_out = high / len(ppl_values)
    return {'novelty_pct': pct_out, 'median_ppl': median}

# Correction functions

def correct_structural(docs, tokenizer):
    corrected = []
    for d in docs:
        ids = tokenizer.encode(d).ids
        if len(ids) <= tokenizer.max_length:
            corrected.append(d)
        else:
            # chunk into sliding windows
            step = int(tokenizer.max_length * 0.9)
            for i in range(0, len(ids), step):
                chunk_ids = ids[i:i + tokenizer.max_length]
                corrected.append(tokenizer.decode(chunk_ids))
    return corrected


def correct_duplicates(docs):
    hashes = td_hash.hash_strings(docs)
    seen = set()
    uniq = []
    for h, d in zip(hashes, docs):
        if h not in seen:
            seen.add(h)
            uniq.append(d)
    return uniq


def correct_language(docs, lang_model, target_lang='en'):
    return [d for d in docs if lang_model.predict(d.replace('\n',' '), k=1)[0][0] == target_lang]


def correct_pii(docs, analyzer):
    masked = []
    for text in docs:
        res = analyzer.analyze(text=text, entities=[], language='en')
        out = text
        for r in res:
            start, end = r.start, r.end
            out = out[:start] + '[REDACTED]' + out[end:]
        masked.append(out)
    return masked


def correct_noise(docs):
    return [d for d in docs if shannon_entropy(d) >= 3 and textstat.flesch_kincaid_grade(d) >= 5]


def correct_novelty(docs, kenlm_model):
    ppl_vals = [(kenlm_model.perplexity(d), d) for d in docs]
    median = sorted(v for v,_ in ppl_vals)[len(ppl_vals)//2]
    kept = []
    for ppl,d in ppl_vals:
        if median/2 <= ppl <= median*2:
            kept.append(d)
    return kept

# Main

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Evaluate and correct a text dataset')
    parser.add_argument('input_dir', type=str, help='Path to dataset folder')
    parser.add_argument('--lang', type=str, default='en', help='Target language code')
    args = parser.parse_args()

    # Load resources
    tok = Tokenizer('mistral')
    lang_model = fasttext.load_model('lid.176.ftz')
    analyzer = RecognizerRegistry()
    # Train KenLM on 1% sample
    docs = load_texts(args.input_dir)
    sample = random.sample(docs, max(1, len(docs)//100))
    with open('sample.txt','w') as f:
        f.write("\n".join(sample))
    os.system('lmplz -o 5 < sample.txt > sample.arpa')
    ken = kenlm.Model('sample.arpa')

    # Initial score
    metrics = {}
    sm = structural_metrics(docs, tok)
    metrics['struct'] = sm['pct_over_context']
    dm = duplication_metrics(docs)
    metrics['dup'] = dm['dup_ratio_exact']
    lm = language_metrics(docs, lang_model, args.lang)
    metrics['lang'] = lm['off_language_pct']
    pm = pii_metrics(docs, analyzer)
    metrics['pii'] = pm['pii_pct']
    nm = noise_metrics(docs)
    metrics['noise'] = nm['low_entropy_pct']
    nov = perplexity_metrics(docs, ken)
    metrics['nov'] = nov['novelty_pct']

    score, subs = compute_score(metrics)
    print(f"Initial Score: {score:.2f}/100")
    print("Subscores:", subs)

    # Sequential corrections
    steps = [
        ('structural', correct_structural, (tok,)),
        ('duplicates', correct_duplicates, ()),
        ('language', correct_language, (lang_model, args.lang)),
        ('pii', correct_pii, (analyzer,)),
        ('noise', correct_noise, ()),
        ('novelty', correct_novelty, (ken,)),
    ]
    for name, func, params in steps:
        docs = func(docs, *params)
        # recompute metrics & score
        metrics['struct'] = structural_metrics(docs, tok)['pct_over_context']
        metrics['dup'] = duplication_metrics(docs)['dup_ratio_exact']
        metrics['lang'] = language_metrics(docs, lang_model, args.lang)['off_language_pct']
        metrics['pii'] = pii_metrics(docs, analyzer)['pii_pct']
        metrics['noise'] = noise_metrics(docs)['low_entropy_pct']
        metrics['nov'] = perplexity_metrics(docs, ken)['novelty_pct']
        score, subs = compute_score(metrics)
        print(f"After {name} correction -> Score: {score:.2f}/100")

    print("Final Score and subscores:")
    print(score, subs)
