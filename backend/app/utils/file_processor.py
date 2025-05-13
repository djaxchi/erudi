import re
import unicodedata

CHUNK_SIZE = 800
OVERLAP = 200
OUTPUT_PATH = "../../data/datasets/dataset.txt"


def extract_text_from_pdf(pdf_path):
    """Extrait le texte brut depuis un PDF avec PyPDF2."""
    text = ""
    with open(pdf_path, "rb") as file:
        reader = pypdf.PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() or ""  # Peut être None si la page est vide
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

def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=OVERLAP):
    """Découpe le texte en chunks de longueur donnée avec recouvrement."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = words[i:i+chunk_size]
        chunks.append(" ".join(chunk))
        i += chunk_size - overlap
    return chunks

def process_pdfs_to_causal_dataset(input_folders):
    all_chunks = []
    pdf_files = [list(Path(input_folder).glob("*.pdf")) for input_folder in input_folders]
    pdf_files = [item for sublist in pdf_files for item in sublist]

    txt_files = [list(Path(input_folder).glob("*.txt")) for input_folder in input_folders]
    txt_files = [item for sublist in txt_files for item in sublist]

    for pdf_path in tqdm(pdf_files, desc="Processing PDFs"):
        raw_text = extract_text_from_pdf(pdf_path)
        clean = clean_text(raw_text)
        chunks = chunk_text(clean)
        all_chunks.extend(chunks)
    
    for txt_path in tqdm(txt_files, desc="Processing TXT files"):
        with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        cleaned = clean_text(text)
        chunks = chunk_text(cleaned)
        all_chunks.extend(chunks)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(chunk.strip() for chunk in all_chunks))