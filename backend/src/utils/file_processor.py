"""File Processing Utilities for Knowledge Base and Training.

This module provides text processing functions for preparing PDF and TXT files
for use in knowledge base (RAG) systems and causal language model fine-tuning.
It handles sentence splitting, token-based chunking, text extraction, cleaning,
and dataset creation with performance logging.

Key Features:
    - Multilingual sentence splitting with Unicode support
    - Token-aware chunking with overlap for embedding models
    - PDF text extraction via pypdf
    - Text normalization (whitespace, accents, non-ASCII)
    - Batch processing with progress tracking
    - Comprehensive performance logging

Functions:
    split_sentences: Split text into sentences using multilingual regex.
    chunk_by_tokens: Create token-limited chunks with overlap for embeddings.
    prepare_for_knowledge_base: Process files into cleaned texts for KB.
    extract_text_from_pdf: Extract raw text from PDF files.
    clean_text: Normalize and clean text for training/embeddings.
    chunk_text: Simple word-based chunking with overlap.
    process_pdfs_to_causal_dataset: Create training dataset from files (stub).

Performance:
    Logs detailed timing for each processing stage (extraction, cleaning,
    chunking, etc.) to help identify bottlenecks in large-scale processing.

Examples:
    >>> # Prepare files for knowledge base (RAG)
    >>> from src.utils.file_processor import prepare_for_knowledge_base
    >>> 
    >>> # Process mix of files and folders
    >>> texts = prepare_for_knowledge_base([
    ...     "/path/to/document.pdf",
    ...     "/path/to/folder/",  # All PDFs/TXTs inside
    ...     {"path": "/path/to/file.txt", "type": "file"}
    ... ])
    >>> print(f"Processed {len(texts)} documents")
    >>> 
    >>> # Chunk text for embeddings
    >>> from src.utils.file_processor import chunk_by_tokens
    >>> 
    >>> long_text = "..." * 10000  # Large document
    >>> chunks = chunk_by_tokens(long_text)
    >>> print(f"Created {len(chunks)} chunks with 15% overlap")

Dependencies:
    - pypdf: PDF text extraction
    - transformers: Tokenizer for chunk sizing
    - sentence_transformers: Embedding model introspection
    - regex: Advanced Unicode sentence splitting

Notes:
    - chunk_by_tokens uses paraphrase-multilingual-MiniLM-L12-v2 as reference
    - Overlap defaults: 15% for chunking, 64 tokens for token-based
    - All functions log processing time and stats via structured logger
"""
import os
import re
from typing import List
import unicodedata
import pypdf
from pathlib import Path
from tqdm import tqdm
from src.core.logging import logger
from datetime import datetime

from typing import List
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

def chunk_by_tokens(text: str) -> List[str]:
    """Create token-limited text chunks with overlap for embedding models.

    Produces chunks sized for sentence transformer models by analyzing the
    target model's tokenizer and max sequence length. Uses character-based
    estimation (3 chars/token) with 15% overlap to ensure continuity across
    chunk boundaries.

    The chunker:
    1. Loads paraphrase-multilingual-MiniLM-L12-v2 to detect limits
    2. Determines safe token count (min of transformer/SBERT limits - 2)
    3. Targets 384 tokens per chunk (conservative for [CLS]/[SEP])
    4. Applies 15% overlap between consecutive chunks
    5. Uses ~3 chars per token as fast approximation

    Args:
        text: Input text to chunk. Length is logged for performance tracking.

    Returns:
        List of text chunk strings, each approximately 384 tokens (1152 chars).
        Empty chunks are filtered out. Overlap creates some redundancy between
        consecutive chunks.

    Examples:
        >>> from src.utils.file_processor import chunk_by_tokens
        >>> 
        >>> # Chunk long document for RAG
        >>> long_text = open("document.txt").read()  # 50,000 characters
        >>> chunks = chunk_by_tokens(long_text)
        >>> print(f"Created {len(chunks)} chunks")  # ~45 chunks with overlap
        >>> 
        >>> # Verify chunk sizes
        >>> avg_len = sum(len(c) for c in chunks) / len(chunks)
        >>> print(f"Average chunk size: {avg_len:.0f} chars")  # ~1152

    Notes:
        - Model: paraphrase-multilingual-MiniLM-L12-v2 (128/256/512 max_seq_length)
        - Target: 384 tokens (conservative to avoid truncation)
        - Overlap: 15% (~58 tokens or 173 chars)
        - Estimation: 3 chars/token works for most languages
        - Performance: Fast character-based slicing, no actual tokenization
        - Model loaded/deleted per call (future: cache tokenizer)

    See Also:
        chunk_text: Simple word-based chunking without token awareness
        prepare_for_knowledge_base: Uses this function for KB preparation
    """
    from transformers import AutoTokenizer
    from sentence_transformers import SentenceTransformer

    MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    embedder = SentenceTransformer(MODEL_NAME)

    # Discover safe max length for this specific model
    # (SBERT often sets model.max_seq_length to 128/256, while the base transformer supports up to 512)
    transformer_limit = getattr(tok, "model_max_length", 512)
    sbert_limit = getattr(embedder, "max_seq_length", transformer_limit)
    del embedder
    del tok
    MAX_TOK = min(transformer_limit, sbert_limit)

    # Use a conservative target (room for [CLS]/[SEP], etc.)
    TARGET_TOK = min(384, MAX_TOK - 2)
    OVERLAP_TOK = 64

    if TARGET_TOK is None:
        TARGET_TOK = TARGET_TOK

    logger.info(f"Starting fast chunking for text of length: {len(text)} chars")
    start_time = datetime.now()
    
    # Simple character-based chunking with 15% overlap
    # Estimate: ~3 chars per token on average
    chars_per_chunk = TARGET_TOK * 3
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
    logger.info(f"Fast chunking completed in {total_time:.3f}s, created {len(chunks)} chunks")
    return chunks


def prepare_for_knowledge_base(input_paths: List[str]) -> List[str]:
    """Process PDF and TXT files into cleaned texts for knowledge base (RAG).

    Accepts a mix of file paths and folder paths, extracts and cleans all
    text content, and returns a list of cleaned text strings ready for
    embedding and FAISS indexing. Handles both individual files and batch
    folder processing with detailed performance logging.

    Processing Pipeline:
    1. **Discovery**: Separate files/folders, glob PDFs/TXTs from folders
    2. **PDF Processing**: extract_text_from_pdf → clean_text per file
    3. **TXT Processing**: Read file → clean_text per file
    4. **Logging**: Times each stage (discovery, extraction, cleaning)

    Args:
        input_paths: List of paths (strings or dicts with 'path'/'type' keys).
            Can contain:
            - Direct file paths: "/path/to/document.pdf"
            - Folder paths: "/path/to/folder/" (all .pdf/.txt inside)
            - Dict format: {"path": "/path", "type": "file"}

    Returns:
        List of cleaned text strings, one per processed file. Order matches
        processing order (all PDFs first, then all TXTs). Empty/failed files
        may produce empty strings (filtered during chunking).

    Examples:
        >>> from src.utils.file_processor import prepare_for_knowledge_base
        >>> 
        >>> # Mix of files and folders
        >>> texts = prepare_for_knowledge_base([
        ...     "/docs/paper.pdf",
        ...     "/docs/notes.txt",
        ...     "/docs/research/",  # All PDFs/TXTs inside
        ...     {"path": "/data/report.pdf", "type": "file"}
        ... ])
        >>> print(f"Processed {len(texts)} files")
        >>> 
        >>> # Use in KB creation workflow
        >>> from src.utils.file_processor import chunk_by_tokens
        >>> all_chunks = []
        >>> for text in texts:
        ...     chunks = chunk_by_tokens(text)
        ...     all_chunks.extend(chunks)
        >>> print(f"Created {len(all_chunks)} chunks for FAISS")

    Notes:
        - PDF extraction: Uses pypdf (may miss text from scanned PDFs)
        - Text cleaning: Removes accents, non-ASCII, control chars
        - Logging: Times discovery, extraction, cleaning per file
        - Performance: ~0.1-2s per PDF depending on size/complexity
        - Errors: Invalid paths logged as warnings, don't crash pipeline
        - Supported formats: Only .pdf and .txt (case-insensitive)

    See Also:
        extract_text_from_pdf: PDF extraction implementation
        clean_text: Text normalization implementation
        chunk_by_tokens: Next step for KB preparation
    """
    logger.info(f"Processing PDFs and TXT files to create a dataset, from folders: {input_paths}")
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
    
    # File discovery phase
    
    discovery_time = (datetime.now() - discovery_start).total_seconds()
    
    logger.info(f"File discovery took {discovery_time:.3f}s - Found {len(pdf_files)} PDFs and {len(txt_files)} TXT files")

    final_list = []
    
    # PDF processing phase
    if pdf_files:
        pdf_start = datetime.now()
        for i, pdf_path in enumerate(tqdm(pdf_files, desc="Processing PDF files")):
            logger.info(f"Processing PDF {i+1}/{len(pdf_files)}: {pdf_path.name}")
            extract_start = datetime.now()
            raw_text = extract_text_from_pdf(pdf_path)
            extract_time = (datetime.now() - extract_start).total_seconds()
            
            clean_start = datetime.now()
            clean = clean_text(raw_text)
            clean_time = (datetime.now() - clean_start).total_seconds()
            
            logger.info(f"PDF {pdf_path.name}: extraction={extract_time:.3f}s, cleaning={clean_time:.3f}s, chars={len(clean)}")
            final_list.append(clean)
        
        pdf_total_time = (datetime.now() - pdf_start).total_seconds()
        logger.info(f"All PDF processing took {pdf_total_time:.3f}s")

    # TXT processing phase
    if txt_files:
        txt_start = datetime.now()
        for i, txt_path in enumerate(tqdm(txt_files, desc="Processing TXT files")):
            logger.info(f"Processing TXT {i+1}/{len(txt_files)}: {txt_path.name}")
            read_start = datetime.now()
            with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            read_time = (datetime.now() - read_start).total_seconds()
            
            clean_start = datetime.now()
            cleaned = clean_text(text)
            clean_time = (datetime.now() - clean_start).total_seconds()
            
            logger.info(f"TXT {txt_path.name}: reading={read_time:.3f}s, cleaning={clean_time:.3f}s, chars={len(cleaned)}")
            final_list.append(cleaned)
        
        txt_total_time = (datetime.now() - txt_start).total_seconds()
        logger.info(f"All TXT processing took {txt_total_time:.3f}s")

    total_time = (datetime.now() - start).total_seconds()
    total_chars = sum(len(text) for text in final_list)
    logger.info(f"File preparation completed in {total_time:.3f}s - {len(final_list)} texts, {total_chars} total characters")
    return final_list


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

def process_pdfs_to_causal_dataset(input_paths, chunk_size = 800, overlap = 200, output_path = "data/training_datasets/"):
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
        output_path: Directory for output file (default: "data/training_datasets/").
            File will be named "data.txt" inside this directory.

    Returns:
        Full path to created dataset file (e.g., "data/training_datasets/data.txt").
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
        

    os.makedirs(output_path, exist_ok=True)
    output_path+="data.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(chunk.strip() for chunk in all_chunks))

    logger.info(f"Dataset created with {len(all_chunks)} chunks in {output_path}. in {datetime.now() - start} seconds")

    return output_path
