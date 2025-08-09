import chardet
from pathlib import Path
from typing import List, Dict, Optional
import logging
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor
import re

class TextExtractor:
    def __init__(self, config: Optional[Dict] = None):
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
    def extract_from_file(self, txt_path: Path) -> Optional[Dict]:
        """Extrait le texte d'un fichier .txt avec détection d'encodage et validation"""
        try:
            # Filtrage préalable
            file_size = txt_path.stat().st_size
            if file_size < 100:  # Ignorer les fichiers trop petits
                self.logger.warning(f"Fichier {txt_path.name} trop petit ({file_size} octets)")
                return {
                    "filename": txt_path.name,
                    "filepath": str(txt_path),
                    "text": "",
                    "file_size": file_size,
                    "line_count": 0,
                    "encoding": "unknown",
                    "encoding_confidence": 0.0,
                    "extraction_method": "skipped_small",
                    "success": False
                }

            # Détection automatique de l'encodage avec charset-normalizer
            from charset_normalizer import detect
            with open(txt_path, 'rb') as f:
                raw_data = f.read()
                encoding_result = detect(raw_data)
                encoding = encoding_result['encoding'] or 'utf-8'
                confidence = encoding_result['confidence'] or 0.0

            # Lecture avec l'encodage détecté
            try:
                with open(txt_path, 'r', encoding=encoding) as f:
                    text = f.read()
            except UnicodeDecodeError:
                # Fallback avec ftfy pour corriger les erreurs d'encodage
                from ftfy import fix_text
                with open(txt_path, 'r', encoding='utf-8', errors='replace') as f:
                    text = fix_text(f.read())
                encoding = 'utf-8 (fallback)'
                confidence = 0.5

            # Validation du contenu
            text = text.strip()
            has_replacement_chars = '�' in text
            word_count = len(text.split())
            alphanumeric_ratio = sum(c.isalnum() for c in text) / max(1, len(text))
            if has_replacement_chars or alphanumeric_ratio < 0.1 or word_count < 10:
                self.logger.warning(f"Fichier {txt_path.name} suspect (remplacement_chars={has_replacement_chars}, alphanumeric_ratio={alphanumeric_ratio:.2f}, words={word_count})")
                return {
                    "filename": txt_path.name,
                    "filepath": str(txt_path),
                    "text": text,
                    "file_size": file_size,
                    "line_count": len(text.splitlines()),
                    "encoding": encoding,
                    "encoding_confidence": confidence,
                    "extraction_method": "suspect",
                    "success": False,
                    "issues": {
                        "has_replacement_chars": has_replacement_chars,
                        "low_alphanumeric_ratio": alphanumeric_ratio < 0.1,
                        "too_short": word_count < 10
                    }
                }

            # Statistiques de base
            line_count = len(text.splitlines())
            
            return {
                "filename": txt_path.name,
                "filepath": str(txt_path),
                "text": text,
                "file_size": file_size,
                "line_count": line_count,
                "word_count": word_count,
                "encoding": encoding,
                "encoding_confidence": confidence,
                "extraction_method": "direct_read",
                "success": True
            }
                    
        except Exception as e:
            self.logger.error(f"Erreur extraction {txt_path.name}: {e}")
            return {
                "filename": txt_path.name,
                "filepath": str(txt_path),
                "text": "",
                "file_size": 0,
                "line_count": 0,
                "encoding": "unknown",
                "encoding_confidence": 0.0,
                "extraction_method": "failed",
                "success": False
            }

    def process_file(self, txt_path: str) -> Dict:
        """Traite un fichier texte pour l'extraction (utilisé pour le parallélisme)."""
        return self.extract_from_file(Path(txt_path))

    def extract_from_directory(self, directory: Path, config: Dict = None) -> List[Dict]:
        """Extrait tous les fichiers .txt d'un répertoire avec parallélisation"""
        # Charger les filtres depuis config
        config = config or {}
        min_file_size = config.get("thresholds", {}).get("min_file_size", 100)
        ignored_dirs = config.get("ignored_dirs", [".git", "__pycache__"])
        allowed_extensions = config.get("allowed_extensions", [".txt"])

        # Filtrer les fichiers
        txt_files = []
        for ext in allowed_extensions:
            txt_files.extend(directory.glob(f"**/*{ext}"))
        
        # Supprimer les doublons et ignorer les dossiers non désirés
        txt_files = list(set(f for f in txt_files if not any(ignored_dir in str(f) for ignored_dir in ignored_dirs)))
        txt_files = [f for f in txt_files if f.stat().st_size >= min_file_size and not f.name.startswith(".")]
        
        if not txt_files:
            self.logger.warning(f"Aucun fichier valide trouvé dans {directory}")
            return []

        # Extraction parallélisée
        documents = []
        failed_extractions = []
        
        with ProcessPoolExecutor() as executor:
            results = list(tqdm(
                executor.map(self.process_file, [str(f) for f in txt_files]),
                total=len(txt_files),
                desc="Extraction fichiers"
            ))
        
        for doc_data in results:
            if doc_data and doc_data["success"]:
                documents.append(doc_data)
            elif doc_data:
                failed_extractions.append((doc_data["filename"], doc_data.get("issues", "unknown")))

        success_count = len(documents)
        total_files = len(txt_files)
        
        self.logger.info(f"Extraction terminée: {success_count}/{total_files} fichiers extraits")
        
        if failed_extractions:
            self.logger.warning(f"Échecs d'extraction: {len(failed_extractions)} fichiers")
            for filename, issue in failed_extractions:
                self.logger.warning(f"Échec {filename}: {issue}")
        
        # Statistiques d'encodage
        encodings = {}
        for doc in documents:
            enc = doc["encoding"].split()[0]
            encodings[enc] = encodings.get(enc, 0) + 1
        
        if encodings:
            self.logger.info(f"Encodages détectés: {dict(encodings)}")
        
        return documents
    
    def get_extraction_stats(self, documents: List[Dict], failed_extractions: List[tuple] = None) -> Dict:
        """Statistiques d'extraction avec analyse des échecs"""
        if not documents and not failed_extractions:
            return {}

        total_size = sum(doc["file_size"] for doc in documents)
        total_chars = sum(len(doc["text"]) for doc in documents)
        total_lines = sum(doc["line_count"] for doc in documents)
        word_counts = [doc.get("word_count", len(doc["text"].split())) for doc in documents]
        
        sizes = [doc["file_size"] for doc in documents]
        sizes.sort()
        
        encodings = {}
        issues = {}
        for doc in documents:
            enc = doc["encoding"].split()[0]
            encodings[enc] = encodings.get(enc, 0) + 1
            if doc.get("issues"):
                for issue, value in doc["issues"].items():
                    issues[issue] = issues.get(issue, 0) + (1 if value else 0)
        
        # Statistiques des échecs
        failure_reasons = {}
        if failed_extractions:
            for _, issue in failed_extractions:
                failure_reasons[str(issue)] = failure_reasons.get(str(issue), 0) + 1
        
        return {
            "total_files": len(documents),
            "failed_files": len(failed_extractions) if failed_extractions else 0,
            "failure_reasons": failure_reasons,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "total_characters": total_chars,
            "total_lines": total_lines,
            "avg_file_size": total_size / len(documents) if documents else 0,
            "avg_characters_per_file": total_chars / len(documents) if documents else 0,
            "avg_words_per_file": sum(word_counts) / len(word_counts) if word_counts else 0,
            "median_file_size": sizes[len(sizes) // 2] if sizes else 0,
            "largest_file_size": max(sizes) if sizes else 0,
            "smallest_file_size": min(sizes) if sizes else 0,
            "word_count_distribution": {
                "min_words": min(word_counts) if word_counts else 0,
                "max_words": max(word_counts) if word_counts else 0,
                "median_words": word_counts[len(word_counts) // 2] if word_counts else 0
            },
            "encodings_distribution": encodings,
            "issues_distribution": issues
        }