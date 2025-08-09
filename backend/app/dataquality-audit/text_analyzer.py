import re
import textstat
from langdetect import detect, detect_langs
from langdetect.lang_detect_exception import LangDetectException as LangDetectError
from typing import Dict, List
import numpy as np
from collections import Counter
import logging
import spacy

class TextAnalyzer:
    def __init__(self, config: Dict = None):
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        logging_level = self.config.get("logging_level", "INFO")
        self.logger.setLevel(getattr(logging, logging_level))
        
    def analyze_document(self, doc: Dict) -> Dict:
        """Analyse complète d'un document"""
        if not doc.get("success", False) or doc.get("issues", {}).get("too_short") or doc.get("issues", {}).get("has_replacement_chars"):
            return self._empty_analysis(doc.get("filename", ""))
        
        text = doc["text"]
        if not text.strip():
            return self._empty_analysis(doc.get("filename", ""))
        
        analysis = {
            "filename": doc["filename"],
            "basic_stats": self._get_basic_stats(text, doc.get("word_count"), doc.get("line_count")),
            "language": self._detect_language(text),
            "readability": self._analyze_readability(text),
            "quality_indicators": self._analyze_quality(text, doc.get("issues", {})),
            "content_type": self._detect_content_type(text),
            "file_info": {
                "file_size": doc.get("file_size", 0),
                "line_count": doc.get("line_count", 0),
                "encoding": doc.get("encoding", "unknown"),
                "encoding_confidence": doc.get("encoding_confidence", 0.0)
            },
            "instruction_format": self._detect_instruction_format(text)
        }
        
        return analysis
    
    def _get_basic_stats(self, text: str, precomputed_word_count: int = None, precomputed_line_count: int = None) -> Dict:
        """Statistiques de base du texte"""
        clean_text = re.sub(r'\s+', ' ', text.strip())
        
        words = [w.strip() for w in clean_text.split() if w.strip()] if precomputed_word_count is None else []
        word_count = precomputed_word_count or len(words)
        
        try:
            nlp = spacy.load("en_core_web_sm", disable=["ner", "lemmatizer"])
            doc = nlp(clean_text[:10000])
            sentences = len(list(doc.sents))
        except:
            sentences = max(1, len(re.findall(r'[.!?]+(?:\s|$)', text)))
        
        tokens = re.findall(r'\b\w+\b', clean_text)
        token_count = len(tokens) or word_count
        
        return {
            "char_count": len(text),
            "word_count": word_count,
            "sentence_count": sentences,
            "token_count": token_count,
            "avg_word_length": np.mean([len(w) for w in words]) if words else 0,
            "avg_sentence_length": word_count / sentences if sentences > 0 else 0,
            "paragraph_count": len(re.findall(r'\n\s*\n', text)) + 1
        }
    
    def _detect_language(self, text: str) -> Dict:
        """Détection de langue avec langdetect"""
        try:
            sample_text = text[:3000].strip()
            if len(sample_text) < 20:
                return {"language": "unknown", "confidence": 0.5, "is_target_language": False}
            
            lang = detect(sample_text)
            confidence = max([prob.prob for prob in detect_langs(sample_text) if prob.lang == lang], default=0.9)
            target_languages = self.config.get("target_languages", ["en", "fr"])
            is_target = lang in target_languages
            
            return {
                "language": lang,
                "confidence": confidence,
                "is_target_language": is_target
            }
        except LangDetectError as e:
            self.logger.warning(f"Erreur détection langue: {e}")
            return {"language": "unknown", "confidence": 0.0, "is_target_language": False}
    
    def _analyze_quality(self, text: str, issues: Dict = None) -> Dict:
        """Indicateurs de qualité du texte"""
        issues = issues or {}
        
        words = re.findall(r'\b\w+\b', text, re.UNICODE)
        words_lower = [w.lower() for w in words] if words else []  # Initialisation précoce
        
        corruption_patterns = [
            re.compile(r'[ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]{20,}', re.UNICODE),
            re.compile(r'Ã[\x80-\xFF]', re.UNICODE),
            re.compile(r'[\x80-\xff]{5,}', re.UNICODE),
            re.compile(r'(\w)\1{6,}', re.UNICODE)
        ]
        
        corruption_count = 0
        for pattern in corruption_patterns:
            matches = pattern.findall(text)
            corruption_count += len(matches)
        
        if issues.get("has_replacement_chars"):
            corruption_count += 50
        
        noise_ratio = min(1.0, corruption_count / max(50, len(words))) if words else 1.0
        
        spam_ratio = 0.0
        try:
            from transformers import pipeline
            spam_classifier = pipeline("text-classification", model="distilbert-base-uncased-finetuned-sst-2-english")
            result = spam_classifier(text[:512])[0]
            spam_score = result["score"]
            spam_ratio = spam_score if result["label"] == "NEGATIVE" else 0.0
        except Exception as e:
            self.logger.warning(f"Erreur détection spam: {e}")
            word_freq = Counter(words_lower)
            spam_indicators = sum(min(5, count - 2) for word, count in word_freq.most_common(20) if len(word) > 2 and count > max(3, len(words_lower) * 0.03))
            spam_words = ['bitcoin', 'crypto', 'buy', 'click', 'urgent', 'now', 'free']
            spam_word_count = sum(words_lower.count(word) for word in spam_words)
            spam_ratio = min(1.0, (spam_indicators + spam_word_count) / 10)
        
        unique_words = len(set(words_lower)) if words_lower else 0
        ttr = unique_words / len(words_lower) if words_lower else 0
        
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        incomplete_count = sum(1 for line in lines if 3 < len(line) < 20 and not re.search(r'[.!?:;]$', line))
        incomplete_ratio = incomplete_count / max(1, len(lines))
        
        caps_count = len(re.findall(r'[A-Z]', text))
        caps_ratio = caps_count / max(1, len(text)) if text else 0
        
        return {
            "noise_ratio": noise_ratio,
            "spam_ratio": spam_ratio,
            "incomplete_ratio": incomplete_ratio,
            "type_token_ratio": ttr,
            "caps_ratio": caps_ratio,
            "has_tables": "│" in text or "┌" in text or "├" in text or text.count("\t") > 5,
            "has_formulas": bool(re.search(r'[∑∫∂√±≤≥≠∞]|[a-zA-Z]\s*=\s*[a-zA-Z0-9]', text)),
            "has_urls": bool(re.search(r'https?://|www\.', text)),
            "has_emails": bool(re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)),
            "has_phone_numbers": bool(re.search(r'(\+\d{1,3}[-.\s]?)?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}', text)),
            "line_count": len(lines),
            "empty_lines_ratio": (len(text.split('\n')) - len(lines)) / max(1, len(text.split('\n'))),
            "encoding_issues": issues.get("has_replacement_chars", False) or corruption_count > 0
        }
    
    def _analyze_readability(self, text: str, language: str = "en") -> Dict:
        """Analyse de lisibilité"""
        try:
            clean_text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)\'\"]', ' ', text).strip()
            if len(clean_text) < 50:
                return {
                    "flesch_score": 0,
                    "flesch_kincaid": 0,
                    "automated_readability": 0,
                    "coleman_liau": 0
                }
            
            if language == "es":
                flesch = textstat.fernandez_huerta(clean_text) if clean_text else 0
            else:
                flesch = textstat.flesch_reading_ease(clean_text)
            
            if not (-100 <= flesch <= 150):
                flesch = 50
            
            return {
                "flesch_score": flesch,
                "flesch_kincaid": textstat.flesch_kincaid_grade(clean_text) if language == "en" else 0,
                "automated_readability": textstat.automated_readability_index(clean_text) if language == "en" else 0,
                "coleman_liau": textstat.coleman_liau_index(clean_text) if language == "en" else 0
            }
        except Exception as e:
            self.logger.warning(f"Erreur calcul lisibilité: {e}")
            return {
                "flesch_score": 50,
                "flesch_kincaid": 0,
                "automated_readability": 0,
                "coleman_liau": 0
            }
    
    def _detect_content_type(self, text: str) -> Dict:
        """Détection de type de contenu"""
        patterns = {
            "dialogue": len(re.findall(r':\s*["\']|^[A-Z][a-z]*\s*:\s|—\s*[A-Z]', text, re.MULTILINE)),
            "questions": len(re.findall(r'\?', text)),
            "instructions": len(re.findall(r'^\s*\d+[\.\)]\s|^[-•*]\s|^[A-Z]\)\s|###\s*Instruction:', text, re.MULTILINE)),
            "code": len(re.findall(r'```|def\s+\w+$$ |class\s+\w+|import\s+\w+|function\s*\(|<[a-zA-Z]+>|{\s*\w+:', text)),
            "references": len(re.findall(r'\[\d+\]|\(\d{4} $$|et al\.|doi:|ISBN|ISSN', text, re.IGNORECASE)),
            "academic": len(re.findall(r'abstract|introduction|methodology|conclusion|bibliography|figure\s+\d+', text, re.IGNORECASE)),
            "legal": len(re.findall(r'article\s+\d+|section\s+\d+|whereas|therefore|pursuant|herein', text, re.IGNORECASE)),
            "technical": len(re.findall(r'algorithm|implementation|system|architecture|configuration|parameter', text, re.IGNORECASE)),
            "qa_pair": len(re.findall(r'Q:\s.*?\nA:\s', text, re.MULTILINE))
        }
        
        token_count = len(re.findall(r'\b\w+\b', text))
        patterns = {k: (v / max(1, token_count)) * 1000 for k, v in patterns.items()} if token_count > 0 else patterns
        
        dominant_type = "generic" if all(v == 0 for v in patterns.values()) else max(patterns.keys(), key=patterns.get)
        
        return {
            "type_indicators": patterns,
            "dominant_type": dominant_type,
            "text_length_category": self._categorize_text_length(token_count)
        }
    
    def _categorize_text_length(self, token_count: int) -> str:
        """Catégorise la longueur du texte"""
        min_tokens = self.config.get("thresholds", {}).get("min_tokens", 50)
        max_tokens = self.config.get("thresholds", {}).get("max_tokens", 8000)
        
        if token_count < min_tokens:
            return "very_short"
        elif token_count < min_tokens * 4:
            return "short"
        elif token_count < min_tokens * 20:
            return "medium"
        elif token_count < max_tokens:
            return "long"
        else:
            return "very_long"
    
    def _detect_instruction_format(self, text: str) -> bool:
        """Vérifie si le texte suit un format d'instruction"""
        patterns = [r'### Instruction:', r'\binstruct\b', r'\[INST\]']
        return any(re.search(pattern, text, re.I) for pattern in patterns)
    
    def _empty_analysis(self, filename: str = "", issues: Dict = None) -> Dict:
        """Analyse par défaut pour texte vide"""
        issues = issues or {}
        return {
            "filename": filename,
            "basic_stats": {"char_count": 0, "word_count": 0, "sentence_count": 0, 
                            "token_count": 0, "avg_word_length": 0, "avg_sentence_length": 0,
                            "paragraph_count": 0},
            "language": {"language": "unknown", "confidence": 0.0, "is_target_language": False},
            "readability": {"flesch_score": 50, "flesch_kincaid": 0, 
                            "automated_readability": 0, "coleman_liau": 0},
            "quality_indicators": {
                "noise_ratio": 1.0, "spam_ratio": 1.0, "incomplete_ratio": 1.0, 
                "type_token_ratio": 0, "caps_ratio": 0, "encoding_issues": issues.get("has_replacement_chars", True),
                "has_tables": False, "has_formulas": False, 
                "has_urls": False, "has_emails": False, "has_phone_numbers": False,
                "line_count": 0, "empty_lines_ratio": 1.0
            },
            "content_type": {"type_indicators": {}, "dominant_type": "empty", "text_length_category": "very_short"},
            "file_info": {"file_size": 0, "line_count": 0, "encoding": "unknown", "encoding_confidence": 0.0},
            "instruction_format": False
        }