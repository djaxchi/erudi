import json
from pathlib import Path
from typing import Dict, List, Optional
import argparse
from datetime import datetime
import numpy as np
import csv
from concurrent.futures import ProcessPoolExecutor
import torch
import logging
import numpy as np

from text_extractor import TextExtractor
from text_analyzer import TextAnalyzer
from quality_scorer import QualityScorer
from similarity_checker import SimilarityChecker

def load_config(config_path: Optional[str] = None) -> Dict:
    """Charge et valide la configuration pour Mistral 7B"""
    default_config = {
        "thresholds": {
            "min_tokens": 50,
            "max_tokens": 8000,
            "min_quality_score": 0.6,
            "min_readability": 30,
            "min_language_confidence": 0.7,
            "similarity_threshold": 0.85
        },
        "scoring": {
            "weights": {
                "quality": 0.4,
                "diversity": 0.2,
                "consistency": 0.2,
                "relevance": 0.2
            }
        },
        "similarity": {
            "model_name": "paraphrase-MiniLM-L6-v2",
            "batch_size": 32,
            "sample_size": 100,
            "device": "cuda" if torch.cuda.is_available() else "cpu"
        },
        "target_languages": ["en", "fr"],
        "preferred_content_types": ["instructions", "qa_pair"]
    }

    logger = logging.getLogger(__name__)
    if config_path:
        try:
            with open(config_path, 'r') as f:
                custom_config = json.load(f)
                default_config.update(custom_config)
                logger.info(f"Configuration chargée depuis {config_path}")
        except Exception as e:
            logger.error(f"Erreur chargement config: {e}")
            logger.info("Utilisation de la configuration par défaut")

    total_weight = sum(default_config["scoring"]["weights"].values())
    if not 0.99 <= total_weight <= 1.01:
        logger.warning(f"Somme des poids ({total_weight}) != 1.0, normalisation appliquée")
        for key in default_config["scoring"]["weights"]:
            default_config["scoring"]["weights"][key] /= total_weight

    for key, value in default_config["thresholds"].items():
        if value < 0:
            logger.warning(f"Seuil invalide {key}: {value}, réinitialisé à 0")
            default_config["thresholds"][key] = 0

    return default_config

def print_header(config: Dict):
    """Affiche l'en-tête du programme"""
    print("=" * 70)
    print(" ANALYSEUR DE QUALITÉ DE DATASET POUR FINE-TUNING")
    print(" Optimisé pour Mistral 7B")
    print(f" Langues cibles: {', '.join(config.get('target_languages', ['en']))}")
    print(f" Modèle de similarité: {config['similarity']['model_name']}")
    print("=" * 70)
    print()

def print_analysis_results(title: str, stats: Dict):
    """Affiche les résultats d'analyse de manière structurée"""
    print("\n" + "="*50)
    print(f" {title.upper()}")
    print("="*50)
    
    print("\nVUE D'ENSEMBLE:")
    print(f"- Documents analysés: {stats['total_docs']:,}")
    print(f"- Caractères totaux: {stats['total_chars']:,}")
    print(f"- Tokens estimés: {stats['total_tokens']:,}")
    print(f"- Taille approximative: {stats['total_size_mb']:.1f} MB")
    
    print("\nQUALITÉ:")
    print(f"- Score moyen: {stats['avg_score']:.2f}/1.0")
    print(f"- Excellents (≥0.8): {stats['excellent']:,}")
    print(f"- Bons (0.6-0.8): {stats['good']:,}")
    print(f"- Moyens (0.4-0.6): {stats['average']:,}")
    print(f"- Faibles (<0.4): {stats['poor']:,}")
    
    print("\nDOUBLONS:")
    print(f"- Documents dupliqués: {stats['duplicate_count']:,}")
    print(f"- Groupes de doublons: {stats['duplicate_groups']:,}")
    print(f"- Diversité: {stats['diversity_score']:.2f}/1.0")
    print(f"- Clusters: {stats['cluster_count']}")
    
    print("\nLANGUES:")
    for lang, (count, pct) in stats['languages'].items():
        print(f"- {lang.upper()}: {count:,} docs ({pct:.1f}%)")
    
    print("\nTYPES DE CONTENU:")
    for ctype, (count, pct) in stats['content_types'].items():
        print(f"- {ctype.title()}: {count:,} docs ({pct:.1f}%)")
    
    print("\nFORMATS D'INSTRUCTION:")
    print(f"- Documents avec format d'instruction: {stats['instruction_count']:,}")
    
    if stats['issues']:
        print("\nPROBLÈMES DÉTECTÉS:")
        for issue in stats['issues']:
            print(f"- {issue}")
    
    print("\n" + "="*50)


def collect_stats(documents: List[Dict], document_scores: List[Dict], 
                 duplicates: List[Dict], similarity_stats: Dict) -> Dict:
    """Collecte les statistiques pour l'affichage - VERSION CORRIGÉE"""
    total_docs = len(documents)
    total_chars = sum(len(doc.get("text", "")) for doc in documents)
    
    total_tokens = 0
    if document_scores:
        for doc_score in document_scores:
            doc_analysis = None
            for analysis in document_scores:
                if analysis.get("filename") == doc_score.get("filename"):
                    doc_analysis = analysis
                    break
            
            if doc_analysis:
                tokens = doc_analysis.get("debug", {}).get("token_count", 0)
                if tokens == 0:  
                    original_doc = next((d for d in documents if d.get("filename") == doc_score.get("filename")), None)
                    if original_doc:
                        text = original_doc.get("text", "")
                        tokens = len(text.split()) if text else 0
                total_tokens += tokens
    
    if total_tokens == 0:
        total_tokens = sum(len(doc.get("text", "").split()) for doc in documents)
    
    scores = [doc["scores"]["overall"] for doc in document_scores] if document_scores else [0]
    avg_score = np.mean(scores) if scores else 0.0
    
    languages = {}
    if document_scores:
        for doc in document_scores:
            lang = "unknown"  
            
            if "language" in doc.get("debug", {}):
                lang = doc["debug"]["language"]
            elif "detected_language" in doc.get("debug", {}):
                lang = doc["debug"]["detected_language"]
            else:
                original_doc = next((d for d in documents if d.get("filename") == doc.get("filename")), None)
                if original_doc and "detected_language" in original_doc:
                    lang = original_doc["detected_language"]
            
            languages[lang] = languages.get(lang, 0) + 1
    
    languages = {k: (v, (v/total_docs)*100) for k, v in sorted(languages.items(), key=lambda x: x[1], reverse=True)[:5]}
    
    content_types = {}
    if document_scores:
        for doc in document_scores:
            ctype = "generic"  # Valeur par défaut
            
            if "content_type" in doc.get("debug", {}):
                ctype = doc["debug"]["content_type"]
            
            content_types[ctype] = content_types.get(ctype, 0) + 1
    
    content_types = {k: (v, (v/total_docs)*100) for k, v in sorted(content_types.items(), key=lambda x: x[1], reverse=True)[:5]}
    
    instruction_count = sum(1 for doc in document_scores if doc.get("debug", {}).get("instruction_format", False))
    
    issues = []
    if total_tokens == 0:
        issues.append("Comptage de tokens défaillant - vérifier text_analyzer.py")
    
    if document_scores:
        spam_count = sum(1 for doc in document_scores if any("spam" in str(issue).lower() for issue in doc.get("issues", [])))
        corruption_count = sum(1 for doc in document_scores if any("corrupt" in str(issue).lower() or "noise" in str(issue).lower() for issue in doc.get("issues", [])))
        encoding_count = sum(1 for doc in document_scores if any("encod" in str(issue).lower() for issue in doc.get("issues", [])))
        
        if spam_count > 0:
            issues.append(f"Contenu spam détecté ({spam_count} documents)")
        if corruption_count > 0:
            issues.append(f"Corruption détectée ({corruption_count} documents)")
        if encoding_count > 0:
            issues.append(f"Problèmes d'encodage ({encoding_count} documents)")
        
        non_target_count = sum(1 for doc in document_scores if any("non cible" in str(issue).lower() or "non target" in str(issue).lower() for issue in doc.get("issues", [])))
        if non_target_count > 0:
            issues.append(f"Documents en langues non cibles ({non_target_count})")
    
    return {
        "total_docs": total_docs,
        "total_chars": total_chars,
        "total_tokens": total_tokens,  # Maintenant correctement calculé
        "total_size_mb": total_chars/1024/1024,
        "avg_score": avg_score,
        "excellent": sum(1 for s in scores if s >= 0.8),
        "good": sum(1 for s in scores if 0.6 <= s < 0.8),
        "average": sum(1 for s in scores if 0.4 <= s < 0.6),
        "poor": sum(1 for s in scores if s < 0.4),
        "duplicate_count": sum(group.get("group_size", 0) for group in duplicates),
        "duplicate_groups": len(duplicates),
        "diversity_score": similarity_stats.get("diversity_score", 0),
        "cluster_count": similarity_stats.get("cluster_count", 0),
        "languages": languages,
        "content_types": content_types,
        "instruction_count": instruction_count,
        "issues": issues
    }

def save_report(output_dir: Path, documents: List[Dict], document_scores: List[Dict], 
                duplicates: List[Dict], similarity_stats: Dict):
    """Sauvegarde un rapport détaillé"""
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": collect_stats(documents, document_scores, duplicates, similarity_stats),
        "document_scores": document_scores,
        "duplicates": duplicates,
        "similarity_stats": similarity_stats
    }
    
    report_path = output_dir / "detailed_analysis_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    csv_path = output_dir / "analysis_summary.csv"
    with open(csv_path, 'w', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "Value"])
        for key, value in report["summary"].items():
            if isinstance(value, dict):
                for subkey, subvalue in value.items():
                    writer.writerow([f"{key}_{subkey}", subvalue])
            else:
                writer.writerow([key, value])
    
    print(f"\nRapport détaillé sauvegardé: {report_path}")
    print(f"Résumé CSV sauvegardé: {csv_path}")

def main():
    parser = argparse.ArgumentParser(description="Analyse de qualité de dataset pour fine-tuning")
    parser.add_argument("input_dir", type=str, help="Répertoire contenant les fichiers .txt")
    parser.add_argument("--output-dir", type=str, default="resultats", help="Répertoire de sortie")
    parser.add_argument("--no-duplicates", action="store_true", help="Ignorer la détection de doublons")
    parser.add_argument("--config", type=str, help="Fichier de configuration JSON")
    
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"Erreur: Le répertoire {input_dir} n'existe pas")
        return
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    config = load_config(args.config)
    print_header(config)
    
    print("Phase 1: Extraction des textes...")
    extractor = TextExtractor()
    documents = extractor.extract_from_directory(input_dir)
    
    if not documents:
        print("Aucun document trouvé ou extrait avec succès")
        return
    
    print(f"{len(documents)} documents extraits")
    
    print("\nPhase 2: Analyse des documents...")
    analyzer = TextAnalyzer(config)
    with ProcessPoolExecutor() as executor:
        document_analysis = list(executor.map(analyzer.analyze_document, documents))
    
    print("\nPhase 3: Évaluation de la qualité...")
    scorer = QualityScorer(config)
    with ProcessPoolExecutor() as executor:
        document_scores = list(executor.map(scorer.score_document, document_analysis))
    
    duplicates = []
    similarity_stats = {"diversity_score": 1.0, "cluster_count": 0}
    
    if not args.no_duplicates:
        print("\nPhase 4: Détection des doublons...")
        similarity_checker = SimilarityChecker(config)
        duplicates = similarity_checker.find_duplicates(document_analysis)
        similarity_stats = similarity_checker.get_similarity_stats(document_analysis)
        #similarity_checker.plot_similarity_distribution(document_analysis, output_dir)
    
    #scorer.plot_score_distribution(document_scores, output_dir)
    
    stats = collect_stats(documents, document_scores, duplicates, similarity_stats)
    print_analysis_results("Résultats de l'analyse", stats)
    save_report(output_dir, documents, document_scores, duplicates, similarity_stats)
    
    print(f"\nAnalyse terminée. Résultats dans: {output_dir}")

if __name__ == "__main__":
    main()