import os
import re
from typing import List
import unicodedata
import pypdf
from pathlib import Path
from tqdm import tqdm
import logging
from datetime import datetime

from typing import List
import regex as re
from transformers import AutoTokenizer
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

tok = AutoTokenizer.from_pretrained(MODEL_NAME)
embedder = SentenceTransformer(MODEL_NAME)

# Discover safe max length for this specific model
# (SBERT often sets model.max_seq_length to 128/256, while the base transformer supports up to 512)
transformer_limit = getattr(tok, "model_max_length", 512)
print(f"Transformer max length: {transformer_limit}")
sbert_limit = getattr(embedder, "max_seq_length", transformer_limit)
print(f"SBERT max length: {sbert_limit}")
del embedder
MAX_TOK = min(transformer_limit, sbert_limit)

# Use a conservative target (room for [CLS]/[SEP], etc.)
TARGET_TOK = min(384, MAX_TOK - 2)
OVERLAP_TOK = 64

# Very light multilingual sentence splitter (works okay across Latin/Cyrillic; falls back on punctuation for CJK)
SENT_SPLIT_RE = re.compile(
    r"(?<=\S[.?!])\s+(?=[\"“”'’»)]*\p{Lu})|(?<=\n{2,})", flags=re.UNICODE
)

def split_sentences(text: str) -> List[str]:
    logging.info(f"Starting sentence splitting for text of length: {len(text)}")
    start_time = datetime.now()
    
    # Normalize whitespace, keep double newlines as paragraph hints
    logging.info("Normalizing whitespace...")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    logging.info(f"Whitespace normalization took: {(datetime.now() - start_time).total_seconds():.3f}s")
    
    # Split sentences
    split_start = datetime.now()
    logging.info("Splitting sentences with regex...")
    parts = SENT_SPLIT_RE.split(text.strip())
    logging.info(f"Regex split took: {(datetime.now() - split_start).total_seconds():.3f}s, found {len(parts)} parts")
    
    # Merge tiny fragments
    merge_start = datetime.now()
    logging.info("Merging small fragments...")
    merged, buf = [], []
    for i, s in enumerate(parts):
        if len(s.strip()) == 0: 
            continue
        buf.append(s)
        if len(" ".join(buf)) > 80:  # simple heuristic
            merged.append(" ".join(buf).strip())
            buf = []
    if buf:
        merged.append(" ".join(buf).strip())
    
    logging.info(f"Fragment merging took: {(datetime.now() - merge_start).total_seconds():.3f}s")
    total_time = (datetime.now() - start_time).total_seconds()
    logging.info(f"Sentence splitting completed in {total_time:.3f}s, result: {len(merged)} sentences")
    return merged

def count_tokens(text: str) -> int:
    count_start = datetime.now()
    result = len(tok.encode(text, add_special_tokens=False))
    count_time = (datetime.now() - count_start).total_seconds()
    if count_time > 0.01:  # Log only if it takes more than 10ms
        logging.info(f"Token counting took {count_time:.3f}s for text of length {len(text)}")
    return result

def chunk_by_tokens(text: str, target_tokens: int = TARGET_TOK, overlap_tokens: int = OVERLAP_TOK) -> List[str]:
    logging.info(f"Starting fast chunking for text of length: {len(text)} chars")
    start_time = datetime.now()
    
    # Simple character-based chunking with 15% overlap
    # Estimate: ~3 chars per token on average
    chars_per_chunk = target_tokens * 3
    overlap_chars = int(chars_per_chunk * 0.15)  # 15% overlap
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = min(start + chars_per_chunk, len(text))
        chunk = text[start:end].strip()
        
        if chunk:  # Only add non-empty chunks
            chunks.append(chunk)
        
        # Move forward by chunk size minus overlap
        start += chars_per_chunk - overlap_chars
        
        # Break if we've reached the end
        if end >= len(text):
            break
    
    total_time = (datetime.now() - start_time).total_seconds()
    logging.info(f"Fast chunking completed in {total_time:.3f}s, created {len(chunks)} chunks")
    return chunks


def prepare_for_knowledge_base(input_paths: List[str]) -> List[str]:
    """Prépare les chemins de fichiers et de dossiers pour la base de connaissances."""
    logging.info(f"Processing PDFs and TXT files to create a dataset, from folders: {input_paths}")
    discovery_start = datetime.now()
    start = datetime.now()
    
    # Separate files and folders
    pdf_files = []
    txt_files = []
    
    for path_item in input_paths:
        # Handle both string paths and path objects with metadata
        if isinstance(path_item, dict):
            path = path_item.get('path')
            path_type = path_item.get('type', 'unknown')
            logging.info(f"Processing {path_type}: {path}")
        else:
            path = path_item
            path_type = 'unknown'
            
        path_obj = Path(path)
        
        if path_obj.is_file():
            # Handle individual files
            if path.lower().endswith('.pdf'):
                pdf_files.append(path_obj)
                logging.info(f"Added PDF file: {path}")
            elif path.lower().endswith('.txt'):
                txt_files.append(path_obj)
                logging.info(f"Added TXT file: {path}")
        elif path_obj.is_dir():
            # Handle folders - search for files inside
            folder_pdfs = list(path_obj.glob("*.pdf"))
            folder_txts = list(path_obj.glob("*.txt"))
            pdf_files.extend(folder_pdfs)
            txt_files.extend(folder_txts)
            logging.info(f"Added from folder {path}: {len(folder_pdfs)} PDFs, {len(folder_txts)} TXTs")
        else:
            logging.warning(f"Path does not exist or is not accessible: {path}")

    logging.info(f"Total files to process: {len(pdf_files)} PDFs, {len(txt_files)} TXTs")
    
    # File discovery phase
    
    discovery_time = (datetime.now() - discovery_start).total_seconds()
    
    logging.info(f"File discovery took {discovery_time:.3f}s - Found {len(pdf_files)} PDFs and {len(txt_files)} TXT files")

    final_list = []
    
    # PDF processing phase
    if pdf_files:
        pdf_start = datetime.now()
        for i, pdf_path in enumerate(tqdm(pdf_files, desc="Processing PDF files")):
            logging.info(f"Processing PDF {i+1}/{len(pdf_files)}: {pdf_path.name}")
            extract_start = datetime.now()
            raw_text = extract_text_from_pdf(pdf_path)
            extract_time = (datetime.now() - extract_start).total_seconds()
            
            clean_start = datetime.now()
            clean = clean_text(raw_text)
            clean_time = (datetime.now() - clean_start).total_seconds()
            
            logging.info(f"PDF {pdf_path.name}: extraction={extract_time:.3f}s, cleaning={clean_time:.3f}s, chars={len(clean)}")
            final_list.append(clean)
        
        pdf_total_time = (datetime.now() - pdf_start).total_seconds()
        logging.info(f"All PDF processing took {pdf_total_time:.3f}s")

    # TXT processing phase
    if txt_files:
        txt_start = datetime.now()
        for i, txt_path in enumerate(tqdm(txt_files, desc="Processing TXT files")):
            logging.info(f"Processing TXT {i+1}/{len(txt_files)}: {txt_path.name}")
            read_start = datetime.now()
            with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            read_time = (datetime.now() - read_start).total_seconds()
            
            clean_start = datetime.now()
            cleaned = clean_text(text)
            clean_time = (datetime.now() - clean_start).total_seconds()
            
            logging.info(f"TXT {txt_path.name}: reading={read_time:.3f}s, cleaning={clean_time:.3f}s, chars={len(cleaned)}")
            final_list.append(cleaned)
        
        txt_total_time = (datetime.now() - txt_start).total_seconds()
        logging.info(f"All TXT processing took {txt_total_time:.3f}s")

    total_time = (datetime.now() - start).total_seconds()
    total_chars = sum(len(text) for text in final_list)
    logging.info(f"File preparation completed in {total_time:.3f}s - {len(final_list)} texts, {total_chars} total characters")
    return final_list


def extract_text_from_pdf(pdf_path):
    """Extrait le texte brut depuis un PDF avec PyPDF2."""
    text = ""
    with open(pdf_path, "rb") as file:
        reader = pypdf.PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() or ""
            text += "\n"
    return text


def clean_text(text):
    """Nettoie le texte de manière plus ciblée pour fine-tuning."""
    # Normalise les caractères Unicode pour décomposer les accents
    text = unicodedata.normalize('NFKD', text)
    # Supprime les marques diacritiques combinantes
    text = re.sub(r'[\u0300-\u036F]', '', text)
    # Remplace les espaces multiples par un seul espace
    text = re.sub(r"\s+", " ", text)
    # Supprime les caractères de contrôle
    text = re.sub(r"[\x00-\x1F\x7F-\x9F]", "", text)
    # Remplace les caractères non-ASCII restants par un espace
    text = re.sub(r"[^\x00-\x7F]+", " ", text)
    
    return text.strip()

def chunk_text(text, chunk_size, overlap):
    """Découpe le texte en chunks de longueur donnée avec recouvrement."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = words[i:i+chunk_size]
        chunks.append(" ".join(chunk))
        i += chunk_size - overlap
    return chunks

def process_pdfs_to_causal_dataset(input_paths, chunk_size = 800, overlap = 200, output_path = "data/training_datasets/"):
    
    logging.info(f"Processing PDFs and TXT files to create a dataset, from paths: {input_paths}")
    start = datetime.now()
    all_chunks = []
    
    # Separate files and folders
    pdf_files = []
    txt_files = []
    
    for path_item in input_paths:
        # Handle both string paths and path objects with metadata
        if isinstance(path_item, dict):
            path = path_item.get('path')
            path_type = path_item.get('type', 'unknown')
            logging.info(f"Processing {path_type}: {path}")
        else:
            path = path_item
            path_type = 'unknown'
            
        path_obj = Path(path)
        
        if path_obj.is_file():
            # Handle individual files
            if path.lower().endswith('.pdf'):
                pdf_files.append(path_obj)
                logging.info(f"Added PDF file: {path}")
            elif path.lower().endswith('.txt'):
                txt_files.append(path_obj)
                logging.info(f"Added TXT file: {path}")
        elif path_obj.is_dir():
            # Handle folders - search for files inside
            folder_pdfs = list(path_obj.glob("*.pdf"))
            folder_txts = list(path_obj.glob("*.txt"))
            pdf_files.extend(folder_pdfs)
            txt_files.extend(folder_txts)
            logging.info(f"Added from folder {path}: {len(folder_pdfs)} PDFs, {len(folder_txts)} TXTs")
        else:
            logging.warning(f"Path does not exist or is not accessible: {path}")

    logging.info(f"Total files to process: {len(pdf_files)} PDFs, {len(txt_files)} TXTs")

    for pdf_path in tqdm(pdf_files, desc="Processing PDF files"):
        raw_text = extract_text_from_pdf(pdf_path)
        clean = clean_text(raw_text)
        chunks = chunk_text(text=clean, chunk_size=chunk_size, overlap=overlap)
        all_chunks.extend(chunks)
    
    for txt_path in tqdm(txt_files, desc="Processing TXT files"):
        with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        cleaned = clean_text(text)
        chunks = chunk_text(cleaned, chunk_size=chunk_size, overlap=overlap)
        all_chunks.extend(chunks)
        

    os.makedirs(output_path, exist_ok=True)
    output_path+="data.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(chunk.strip() for chunk in all_chunks))

    logging.info(f"Dataset created with {len(all_chunks)} chunks in {output_path}. in {datetime.now() - start} seconds")

    return output_path
