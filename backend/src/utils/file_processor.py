"""File Processing Utilities for the TRAINING pipeline.

This module prepares PDF and TXT files for causal language model
fine-tuning: sentence splitting, text extraction, cleaning, word-based
chunking, and dataset creation with performance logging.

KB ingestion does NOT live here anymore — the RAG pipeline (extraction →
non-destructive cleaning → token-accurate chunking) is ``src.ingestion``.

Functions:
    split_sentences: Split text into sentences using multilingual regex.
    extract_text_from_pdf: Extract raw text from PDF files.
    clean_text: Normalize and clean text for training datasets.
    chunk_text: Simple word-based chunking with overlap.
    process_pdfs_to_causal_dataset: Create training dataset from files (stub).

Dependencies:
    - pypdf: PDF text extraction
    - regex: Advanced Unicode sentence splitting
"""
from typing import List
import unicodedata
import pypdf
from pathlib import Path
from tqdm import tqdm
from src.core.logging import logger
from src.core import config
from datetime import datetime

import regex as re


def split_sentences(text: str) -> List[str]:
    """Split text into sentences using multilingual Unicode-aware regex.

    Performs lightweight sentence boundary detection across Latin, Cyrillic,
    and other scripts. Uses punctuation and uppercase detection to identify
    sentence boundaries, with special handling for paragraph breaks.

    The splitter:
    1. Normalizes whitespace (single spaces, preserves double newlines)
    2. Splits on sentence terminators (.?!) followed by uppercase
    3. Merges fragments shorter than 80 characters to avoid micro-chunks
    4. Logs detailed performance metrics for each stage

    Args:
        text: Input text to split into sentences. Can be any Unicode string.

    Returns:
        List of sentence strings, each at least 80 characters (merged from
        smaller fragments). Empty strings are filtered out.

    Examples:
        >>> from src.utils.file_processor import split_sentences
        >>> 
        >>> text = "First sentence. Second sentence! Third one?\\n\\nNew paragraph."
        >>> sentences = split_sentences(text)
        >>> print(len(sentences))  # Varies based on merge logic
        >>> 
        >>> # Handles multilingual text
        >>> text = "Première phrase. Вторая фраза. Third sentence."
        >>> sentences = split_sentences(text)

    Notes:
        - Regex pattern: Splits after .?! + whitespace + uppercase letter
        - Paragraph hints: Double newlines preserved as split points
        - Performance: Logs normalization, splitting, and merging times
        - Limitation: May not work perfectly with CJK languages (no spaces)
    """
    # Very light multilingual sentence splitter (works okay across Latin/Cyrillic; falls back on punctuation for CJK)
    SENT_SPLIT_RE = re.compile(
        r"(?<=\S[.?!])\s+(?=[\"“”'’»)]*\p{Lu})|(?<=\n{2,})", flags=re.UNICODE
    )
    logger.info(f"Starting sentence splitting for text of length: {len(text)}")
    start_time = datetime.now()
    
    # Normalize whitespace, keep double newlines as paragraph hints
    logger.info("Normalizing whitespace...")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    logger.info(f"Whitespace normalization took: {(datetime.now() - start_time).total_seconds():.3f}s")
    
    # Split sentences
    split_start = datetime.now()
    logger.info("Splitting sentences with regex...")
    parts = SENT_SPLIT_RE.split(text.strip())
    logger.info(f"Regex split took: {(datetime.now() - split_start).total_seconds():.3f}s, found {len(parts)} parts")
    
    # Merge tiny fragments
    merge_start = datetime.now()
    logger.info("Merging small fragments...")
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
    
    logger.info(f"Fragment merging took: {(datetime.now() - merge_start).total_seconds():.3f}s")
    total_time = (datetime.now() - start_time).total_seconds()
    logger.info(f"Sentence splitting completed in {total_time:.3f}s, result: {len(merged)} sentences")
    return merged





def extract_text_from_pdf(pdf_path):
    """Extract raw text from PDF file using pypdf.

    Reads all pages from a PDF and concatenates extracted text with newline
    separators. Suitable for text-based PDFs (not scanned images without OCR).

    Args:
        pdf_path: Path to PDF file (string or Path object). Must exist and
            be readable. Can be relative or absolute path.

    Returns:
        String containing all extracted text from all pages, with newlines
        between pages. May be empty if PDF has no extractable text (e.g.,
        scanned images, protected PDFs).

    Examples:
        >>> from src.utils.file_processor import extract_text_from_pdf
        >>> 
        >>> text = extract_text_from_pdf("/docs/paper.pdf")
        >>> print(f"Extracted {len(text)} characters")
        >>> 
        >>> # Check if extraction was successful
        >>> if text.strip():
        ...     print("PDF has extractable text")
        ... else:
        ...     print("PDF may be scanned or empty")

    Notes:
        - Uses pypdf.PdfReader for extraction
        - Adds newline after each page
        - Returns empty string for pages without text
        - No OCR: Scanned PDFs return empty/minimal text
        - Errors: File not found or corrupted PDFs raise pypdf exceptions

    See Also:
        prepare_for_knowledge_base: Calls this for PDF processing
        clean_text: Next step to normalize extracted text
    """
    text = ""
    with open(pdf_path, "rb") as file:
        reader = pypdf.PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() or ""
            text += "\n"
    return text


def clean_text(text):
    """Normalize and clean text for training and embedding use.

    Performs aggressive text normalization to create consistent input for
    language models and embedding models. Removes accents, non-ASCII chars,
    control characters, and normalizes whitespace.

    Cleaning Steps:
    1. **Unicode normalization**: NFKD decomposition (separate base + accents)
    2. **Remove accents**: Strip combining diacritical marks (\\u0300-\\u036F)
    3. **Collapse whitespace**: Replace multiple spaces/tabs/newlines with single space
    4. **Remove control chars**: Strip \\x00-\\x1F and \\x7F-\\x9F
    5. **ASCII-only**: Replace remaining non-ASCII with space
    6. **Trim**: Strip leading/trailing whitespace

    Args:
        text: Raw text to clean (from PDF, TXT, or other source). Can contain
            any Unicode characters, including emojis, special symbols, etc.

    Returns:
        Cleaned ASCII-only string with normalized whitespace. All accents
        removed (e.g., "café" → "cafe"), control characters stripped, single
        spaces between words.

    Examples:
        >>> from src.utils.file_processor import clean_text
        >>> 
        >>> # Remove accents and normalize
        >>> raw = "Café résumé naïve   multiple    spaces"
        >>> clean = clean_text(raw)
        >>> print(clean)  # "Cafe resume naive multiple spaces"
        >>> 
        >>> # Strip emojis and special chars
        >>> raw = "Hello 👋 world! \\t\\n\\n Special chars: ©®™"
        >>> clean = clean_text(raw)
        >>> print(clean)  # "Hello world! Special chars:"

    Notes:
        - Destructive: Loses accents, emojis, and non-Latin scripts
        - Use case: English-centric models or ASCII-only training
        - Multilingual: Consider keeping accents for non-English models
        - Performance: Fast regex-based cleaning
        - Output: Always ASCII (0x00-0x7F only)

    See Also:
        prepare_for_knowledge_base: Uses this for all extracted text
        process_pdfs_to_causal_dataset: Uses this for training data
    """
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
    """Split text into word-based chunks with overlap.

    Simple word-level chunking using whitespace splitting and sliding window.
    Used for creating training datasets or fallback chunking when token-aware
    chunking is not needed.

    Args:
        text: Input text to chunk. Will be split on whitespace.
        chunk_size: Number of words per chunk (not tokens or characters).
        overlap: Number of words to overlap between consecutive chunks.

    Returns:
        List of text chunk strings, each containing approximately chunk_size
        words. Last chunk may be shorter if remaining words < chunk_size.

    Examples:
        >>> from src.utils.file_processor import chunk_text
        >>> 
        >>> text = "word " * 1000  # 1000 words
        >>> chunks = chunk_text(text, chunk_size=100, overlap=20)
        >>> print(len(chunks))  # ~13 chunks (1000/(100-20) + 1)
        >>> 
        >>> # Verify overlap
        >>> print(chunks[0].split()[-5:])  # Last 5 words of first chunk
        >>> print(chunks[1].split()[:5])   # First 5 words of second chunk
        >>> # Some words appear in both due to overlap

    Notes:
        - Word-based: Splits on any whitespace (spaces, tabs, newlines)
        - Not token-aware: 100 words ≠ 100 tokens for most models
        - Overlap: Creates redundancy between chunks for context continuity
        - Performance: Very fast, no model loading needed
        - Use case: Training data preparation or simple RAG chunking

    See Also:
        chunk_by_tokens: Token-aware chunking for embedding models
        process_pdfs_to_causal_dataset: Uses this for training datasets
    """
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = words[i:i+chunk_size]
        chunks.append(" ".join(chunk))
        i += chunk_size - overlap
    return chunks

def process_pdfs_to_causal_dataset(input_paths, chunk_size = 800, overlap = 200, output_path = None):
    """Create causal language model training dataset from PDF/TXT files (STUB).

    Processes PDF and TXT files into word-based chunks and writes them to a
    single text file for causal LM fine-tuning. Each chunk becomes one line
    in the output file. Currently a basic implementation with simple chunking.

    Processing Pipeline:
    1. **Discovery**: Separate files/folders, glob .pdf/.txt from folders
    2. **Extraction**: extract_text_from_pdf for PDFs, read() for TXTs
    3. **Cleaning**: clean_text normalization
    4. **Chunking**: chunk_text with word-based overlap
    5. **Output**: Write all chunks to single text file (one per line)

    Args:
        input_paths: List of paths (strings or dicts with 'path'/'type' keys).
            Same format as prepare_for_knowledge_base.
        chunk_size: Number of words per chunk (default: 800). Affects how
            text is split for training examples.
        overlap: Number of words to overlap between chunks (default: 200).
            Provides context continuity across chunk boundaries.
        output_path: Directory for output file (default: config.TRAINING_DATASETS_DIR).
            File will be named "data.txt" inside this directory.

    Returns:
        Full path to created dataset file (e.g., "backend/data/training_datasets/data.txt").
        File contains one chunk per line, newline-separated.

    Examples:
        >>> from src.utils.file_processor import process_pdfs_to_causal_dataset
        >>> 
        >>> # Create training dataset from folder
        >>> dataset_path = process_pdfs_to_causal_dataset(
        ...     input_paths=["/training_docs/"],
        ...     chunk_size=500,
        ...     overlap=100,
        ...     output_path="data/my_dataset/"
        ... )
        >>> print(f"Dataset created at: {dataset_path}")
        >>> 
        >>> # Read resulting dataset
        >>> with open(dataset_path) as f:
        ...     lines = f.readlines()
        >>> print(f"Dataset has {len(lines)} training examples")

    Notes:
        - STUB STATUS: Basic implementation, future improvements planned
        - Word-based chunking: Not token-aware, may need adjustment per model
        - Output format: Plain text, one chunk per line (not JSON/JSONL)
        - Use case: Causal LM fine-tuning (GPT-style), not instruction tuning
        - Performance: Logs total chunks and processing time
        - File handling: Creates output directory if not exists

    See Also:
        prepare_for_knowledge_base: Similar but for RAG (returns list, no file)
        chunk_text: Chunking implementation used here
        clean_text: Text normalization used here

    TODO:
        - Add support for instruction-tuning format (Q&A pairs)
        - Implement token-based chunking instead of word-based
        - Add data validation and quality checks
        - Support multiple output formats (JSON, JSONL, Parquet)
    """
    
    logger.info(f"Processing PDFs and TXT files to create a dataset, from paths: {input_paths}")
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
            logger.info(f"Processing {path_type}: {path}")
        else:
            path = path_item
            path_type = 'unknown'
            
        path_obj = Path(path)
        
        if path_obj.is_file():
            # Handle individual files
            if path.lower().endswith('.pdf'):
                pdf_files.append(path_obj)
                logger.info(f"Added PDF file: {path}")
            elif path.lower().endswith('.txt'):
                txt_files.append(path_obj)
                logger.info(f"Added TXT file: {path}")
        elif path_obj.is_dir():
            # Handle folders - search for files inside
            folder_pdfs = list(path_obj.glob("*.pdf"))
            folder_txts = list(path_obj.glob("*.txt"))
            pdf_files.extend(folder_pdfs)
            txt_files.extend(folder_txts)
            logger.info(f"Added from folder {path}: {len(folder_pdfs)} PDFs, {len(folder_txts)} TXTs")
        else:
            logger.warning(f"Path does not exist or is not accessible: {path}")

    logger.info(f"Total files to process: {len(pdf_files)} PDFs, {len(txt_files)} TXTs")

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
        
    # Use config.TRAINING_DATASETS_DIR if output_path not specified
    if output_path is None:
        output_dir = config.TRAINING_DATASETS_DIR
    else:
        output_dir = Path(output_path)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "data.txt"
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(chunk.strip() for chunk in all_chunks))

    logger.info(f"Dataset created with {len(all_chunks)} chunks in {output_file}. in {datetime.now() - start} seconds")

    return str(output_file)
