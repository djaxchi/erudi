import os
import re
import unicodedata
import pypdf
from pathlib import Path
from tqdm import tqdm
import logging
from datetime import datetime



def extract_text_from_pdf(pdf_path):
    """Extrait le texte brut depuis un PDF avec PyPDF2."""
    text = ""
    with open(pdf_path, "rb") as file:
        reader = pypdf.PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() or ""
            logging.info(f"Extracted text from page : {page.extract_text()}")
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

def process_pdfs_to_causal_dataset(input_folders, chunk_size = 800, overlap = 200, output_path = "../../data/training_datasets/"):
    
    logging.info(f"Processing PDFs and TXT files to create a dataset, from folders: {input_folders}")
    start = datetime.now()
    all_chunks = []
    pdf_files = [list(Path(input_folder).glob("*.pdf")) for input_folder in input_folders]
    pdf_files = [item for sublist in pdf_files for item in sublist]
    logging.info(f"PDF files found: {pdf_files}")

    txt_files = [list(Path(input_folder).glob("*.txt")) for input_folder in input_folders]
    txt_files = [item for sublist in txt_files for item in sublist]
    logging.info(f"TXT files found: {txt_files}")

    for pdf_path in tqdm(pdf_files, desc="Processing PDF files"):
        raw_text = extract_text_from_pdf(pdf_path)
        logging.info(f"Extracted text from {pdf_path}: {raw_text}")
        clean = clean_text(raw_text)
        logging.info(f"Cleaned text: {clean}")
        chunks = chunk_text(text=clean, chunk_size=chunk_size, overlap=overlap)
        logging.info(f"Chunks created: {chunks}")
        all_chunks.extend(chunks)
        break
    
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
