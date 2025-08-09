# quality_scorer.py - VERSION CORRIGÉE STRICTE
import numpy as np
from typing import Dict, List
import logging
import re

class QualityScorer:
    def __init__(self, config: Dict):
        self.config = config
        self.weights = config["scoring"]["weights"]
        self.thresholds = config["thresholds"]
        self.logger = logging.getLogger(__name__)
        
        # Validation des poids
        total_weight = sum(self.weights.values())
        if not 0.99 <= total_weight <= 1.01:
            self.logger.warning(f"Somme des poids ({total_weight}) != 1.0, normalisation appliquée")
            for key in self.weights:
                self.weights[key] /= total_weight
                
        self.min_language_confidence = self.thresholds.get("min_language_confidence", 0.7)
        self.preferred_content_types = self.config.get("preferred_content_types", ["instructions", "qa_pair"])
        
        # Seuils stricts pour éliminer les datasets corrompus
        self.corruption_threshold = 0.15  # Seuil de corruption acceptable
        self.spam_threshold = 0.3        # Seuil de spam acceptable
        self.min_readability = 20        # Score Flesch minimum
    
    def score_document(self, analysis: Dict) -> Dict:
        """Score de qualité d'un document avec validation stricte"""
        filename = analysis.get("filename", "unknown")
        
        # Court-circuiter immédiatement les documents invalides
        if self._is_document_invalid(analysis):
            return self._create_invalid_document_score(analysis)
        
        # Scores individuels avec validation stricte
        quality_score = self._calculate_quality_score_strict(analysis)
        diversity_score = self._calculate_diversity_score(analysis)
        consistency_score = self._calculate_consistency_score(analysis)
        relevance_score = self._calculate_relevance_score(analysis)
        
        # Application de malus drastiques pour contenu corrompu
        corruption_malus = self._calculate_corruption_malus(analysis)
        
        # Normalisation avec application du malus de corruption
        quality_score = max(0.0, min(1.0, quality_score - corruption_malus))
        diversity_score = max(0.0, min(1.0, diversity_score))
        consistency_score = max(0.0, min(1.0, consistency_score))
        relevance_score = max(0.0, min(1.0, relevance_score))
        
        # Score global pondéré
        overall_score = (
            quality_score * self.weights["quality"] +
            diversity_score * self.weights["diversity"] +
            consistency_score * self.weights["consistency"] +
            relevance_score * self.weights["relevance"]
        )
        
        # Malus supplémentaire pour les documents manifestement corrompus
        if self._is_severely_corrupted(analysis):
            overall_score *= 0.1  # Réduction drastique
            
        return {
        "filename": filename,
        "scores": {
            "quality": quality_score,
            "diversity": diversity_score,
            "consistency": consistency_score,
            "relevance": relevance_score,
            "overall": max(0.0, min(1.0, overall_score))
        },
        "recommendation": self._get_recommendation_strict(overall_score, analysis),
        "issues": self._identify_issues_comprehensive(analysis),
        "debug": {
            "ttr": analysis["quality_indicators"].get("type_token_ratio", 0),
            "flesch": analysis["readability"].get("flesch_score", 0),
            "noise_ratio": analysis["quality_indicators"].get("noise_ratio", 0),
            "spam_ratio": analysis["quality_indicators"].get("spam_ratio", 0),
            "corruption_malus": corruption_malus,
            "language_confidence": analysis["language"].get("confidence", 0),
            "instruction_format": analysis.get("instruction_format", False),
            "token_count": analysis["basic_stats"].get("token_count", 0),  # AJOUT CRITIQUE
            "detected_language": analysis["language"].get("language", "unknown"),  # AJOUT
            "content_type": analysis["content_type"].get("dominant_type", "generic")  # AJOUT
        }
    }
    
    def _is_document_invalid(self, analysis: Dict) -> bool:
        """Vérifie si le document est immédiatement invalide"""
        issues = analysis.get("issues", {})
        basic_stats = analysis.get("basic_stats", {})
        quality_indicators = analysis.get("quality_indicators", {})
        
        # Conditions d'invalidité immédiate
        if (issues.get("too_short") or 
            issues.get("has_replacement_chars") or
            basic_stats.get("token_count", 0) == 0 or
            basic_stats.get("word_count", 0) < 5 or
            quality_indicators.get("noise_ratio", 0) > 0.8):
            return True
            
        return False
    
    def _create_invalid_document_score(self, analysis: Dict) -> Dict:
        """Crée un score pour un document invalide"""
        return {
            "filename": analysis.get("filename", "unknown"),
            "scores": {
                "quality": 0.0,
                "diversity": 0.0,
                "consistency": 0.0,
                "relevance": 0.0,
                "overall": 0.0
            },
            "recommendation": "REJECT - Document invalide ou corrompu",
            "issues": ["Document invalide ou complètement corrompu"] + self._identify_issues_comprehensive(analysis),
            "debug": {
                "ttr": 0,
                "flesch": 0,
                "noise_ratio": 1.0,
                "spam_ratio": 1.0,
                "corruption_malus": 1.0,
                "language_confidence": 0,
                "instruction_format": False
            }
        }
    
    def _calculate_quality_score_strict(self, analysis: Dict) -> float:
        """Score de qualité ULTRA strict - rejet agressif du contenu corrompu"""
        quality_indicators = analysis["quality_indicators"]
        readability = analysis["readability"]
        file_info = analysis["file_info"]
        
        # Récupération des métriques avec valeurs par défaut
        noise_ratio = quality_indicators.get("noise_ratio", 0)
        spam_ratio = quality_indicators.get("spam_ratio", 0)
        incomplete_ratio = quality_indicators.get("incomplete_ratio", 0)
        caps_ratio = quality_indicators.get("caps_ratio", 0)
        
        # REJET IMMÉDIAT pour contenu manifestement corrompu
        if (noise_ratio > 0.1 or spam_ratio > 0.2 or caps_ratio > 0.15):
            return 0.0
        
        # Pénalités exponentielles - plus le ratio est haut, plus la pénalité explose
        noise_penalty = min((noise_ratio * 20) ** 1.5, 0.95)
        spam_penalty = min((spam_ratio * 8) ** 1.2, 0.9)  
        incomplete_penalty = min((incomplete_ratio * 3) ** 1.1, 0.8)
        caps_penalty = min((max(0, caps_ratio - 0.02) * 15) ** 1.3, 0.8)
        
        # Pénalité d'encodage très lourde
        encoding_penalty = 0.0
        if (quality_indicators.get("encoding_issues", False) or 
            file_info.get("encoding_confidence", 1.0) < 0.9):
            encoding_penalty = 0.6
            
        # Score de lisibilité TRÈS strict
        flesch_score = readability.get("flesch_score", 0)
        if flesch_score <= 10:
            readability_factor = 0.0  # Illisible = rejet
        elif flesch_score <= 30:
            readability_factor = 0.1
        elif flesch_score <= 50:
            readability_factor = 0.4
        elif flesch_score <= 70:
            readability_factor = 0.8
        elif flesch_score <= 85:
            readability_factor = 1.0
        else:
            readability_factor = 0.5  # Trop simple
            
        # Score de base très strict (minimum quasi-nul)
        total_penalty = noise_penalty + spam_penalty + incomplete_penalty + caps_penalty + encoding_penalty
        base_score = max(0.001, 1.0 - total_penalty)
        
        # Si trop de pénalités, score = 0
        if total_penalty > 0.8:
            return 0.0
            
        final_score = base_score * readability_factor
        
        # Seuil de rejet final
        if final_score < 0.05:
            return 0.0
            
        return max(0.0, min(1.0, final_score))
    
    def _calculate_corruption_malus(self, analysis: Dict) -> float:
        """Calcule un malus pour la corruption détectée"""
        quality_indicators = analysis["quality_indicators"]
        
        malus = 0.0
        
        # Malus pour corruption sévère
        if quality_indicators.get("noise_ratio", 0) > self.corruption_threshold:
            malus += 0.5
            
        # Malus pour spam détecté
        if quality_indicators.get("spam_ratio", 0) > self.spam_threshold:
            malus += 0.4
            
        # Malus pour problèmes d'encodage
        if quality_indicators.get("encoding_issues", False):
            malus += 0.3
            
        # Malus pour contenu suspect (URLs, emails en masse)
        if (quality_indicators.get("has_urls", False) and 
            quality_indicators.get("has_emails", False)):
            malus += 0.2
            
        return min(malus, 0.9)  # Limiter le malus total
    
    def _is_severely_corrupted(self, analysis: Dict) -> bool:
        """Détecte la corruption sévère nécessitant un rejet IMMÉDIAT"""
        quality_indicators = analysis["quality_indicators"]
        basic_stats = analysis["basic_stats"]
        
        # Critères de rejet IMMÉDIAT (très stricts)
        severe_corruption = (
            quality_indicators.get("noise_ratio", 0) > 0.05 or  # Très peu de tolérance au bruit
            quality_indicators.get("spam_ratio", 0) > 0.15 or   # Très peu de tolérance au spam
            quality_indicators.get("caps_ratio", 0) > 0.12 or   # Moins de tolérance aux majuscules
            basic_stats.get("token_count", 0) < 30 or           # Plus strict sur la longueur minimum
            analysis["readability"].get("flesch_score", 50) <= 5 or  # Plus strict sur la lisibilité
            quality_indicators.get("encoding_issues", False)    # Rejet automatique si problème d'encodage
        )
        
        return severe_corruption
    
    def _calculate_diversity_score(self, analysis: Dict) -> float:
        """Score de diversité lexicale (inchangé mais plus strict sur les seuils bas)"""
        ttr = analysis["quality_indicators"].get("type_token_ratio", 0)
        token_count = analysis["basic_stats"].get("token_count", 0)
        
        # TTR minimum plus élevé
        min_ttr = 0.1 if token_count < 200 else 0.15
        max_ttr = 0.8 if token_count < 200 else 0.9
        
        if ttr < min_ttr:
            return 0.05  # Score très bas pour diversité insuffisante
        elif ttr < min_ttr * 2:
            return 0.1 + (ttr - min_ttr) * 2
        elif ttr < min_ttr * 4:
            return 0.3 + (ttr - min_ttr * 2) * 1.5
        elif ttr <= max_ttr:
            return 0.6 + (ttr - min_ttr * 4) * 1.2
        else:
            return 0.8
    
    def _calculate_consistency_score(self, analysis: Dict) -> float:
        """Score de cohérence (version stricte)"""
        basic_stats = analysis["basic_stats"]
        quality_indicators = analysis["quality_indicators"]
        
        token_count = basic_stats.get("token_count", 0)
        
        # Pénalité plus sévère pour les documents courts
        if token_count < self.thresholds["min_tokens"]:
            length_score = max(0.1, token_count / self.thresholds["min_tokens"])
        elif token_count > self.thresholds["max_tokens"]:
            excess_ratio = (token_count - self.thresholds["max_tokens"]) / self.thresholds["max_tokens"]
            length_score = max(0.2, 1.0 - excess_ratio * 0.6)
        else:
            length_score = 1.0
            
        # Structure plus stricte
        avg_sentence_length = basic_stats.get("avg_sentence_length", 0)
        if 10 <= avg_sentence_length <= 25:
            structure_score = 1.0
        elif 5 <= avg_sentence_length < 10 or 25 < avg_sentence_length <= 35:
            structure_score = 0.6
        else:
            structure_score = 0.3
            
        # Pénalité pour lignes vides excessives
        empty_lines_penalty = min(quality_indicators.get("empty_lines_ratio", 0) * 0.8, 0.4)
        
        final_score = (length_score + structure_score) / 2 - empty_lines_penalty
        return max(0.0, min(1.0, final_score))
    
    def _calculate_relevance_score(self, analysis: Dict) -> float:
        """Score de pertinence (version stricte)"""
        content_type = analysis["content_type"]
        language = analysis["language"]
        quality_indicators = analysis["quality_indicators"]
        
        relevance = 0.3  # Score de base plus bas
        
        # Bonus pour les contenus préférés (réduits)
        type_indicators = content_type.get("type_indicators", {})
        for content_type in self.preferred_content_types:
            if type_indicators.get(content_type, 0) > 2:
                relevance += 0.15
                
        if analysis.get("instruction_format", False):
            relevance += 0.2
            
        # Malus renforcés pour contenus indésirables
        if type_indicators.get("code", 0) > 3:  # Seuil abaissé
            relevance -= 0.25
        if quality_indicators.get("has_urls", False) or quality_indicators.get("has_emails", False):
            relevance -= 0.2
            
        # Pénalités langue plus strictes
        if not language.get("is_target_language", True):
            relevance -= 0.5  # Pénalité plus lourde
        elif language.get("confidence", 0) < self.min_language_confidence:
            relevance -= 0.25
        elif language.get("confidence", 0) > 0.9:
            relevance += 0.15
            
        return max(0.0, min(1.0, relevance))
    
    def _get_recommendation_strict(self, score: float, analysis: Dict) -> str:
        """Recommandations strictes basées sur le score"""
        if self._is_severely_corrupted(analysis):
            return "REJECT - Contenu sévèrement corrompu"
        elif analysis.get("instruction_format", False) and score >= 0.6:
            return "KEEP - Format d'instruction de qualité"
        elif score >= 0.8:
            return "KEEP - Excellente qualité"
        elif score >= 0.65:
            return "KEEP - Bonne qualité"
        elif score >= 0.45:
            return "REVIEW - Qualité moyenne, nettoyage requis"
        elif score >= 0.25:
            return "CLEAN - Nécessite nettoyage intensif"
        else:
            return "REJECT - Qualité insuffisante"
    
    def _identify_issues_comprehensive(self, analysis: Dict) -> List[str]:
        """Identification complète des problèmes"""
        issues = list(analysis.get("issues", []))  # Récupérer les issues existantes
        quality = analysis["quality_indicators"]
        basic_stats = analysis["basic_stats"]
        readability = analysis["readability"]
        language = analysis["language"]
        
        # Issues de qualité
        if quality.get("noise_ratio", 0) > 0.05:
            issues.append(f"Taux de corruption élevé ({quality['noise_ratio']:.2f})")
        if quality.get("spam_ratio", 0) > 0.1:
            issues.append(f"Contenu spam détecté ({quality['spam_ratio']:.2f})")
        if quality.get("incomplete_ratio", 0) > 0.2:
            issues.append(f"Lignes incomplètes ({quality['incomplete_ratio']:.2f})")
        if quality.get("caps_ratio", 0) > 0.05:
            issues.append(f"Excès de majuscules ({quality['caps_ratio']:.2f})")
        if quality.get("encoding_issues", False):
            issues.append("Problèmes d'encodage détectés")
            
        # Issues de taille
        token_count = basic_stats.get("token_count", 0)
        if token_count < self.thresholds["min_tokens"]:
            issues.append(f"Document trop court ({token_count} tokens)")
        elif token_count > self.thresholds["max_tokens"]:
            issues.append(f"Document trop long ({token_count} tokens)")
            
        # Issues de lisibilité
        flesch_score = readability.get("flesch_score", 50)
        if flesch_score < self.min_readability:
            issues.append(f"Texte illisible (Flesch: {flesch_score:.1f})")
        elif flesch_score > 95:
            issues.append(f"Texte trop simpliste (Flesch: {flesch_score:.1f})")
            
        # Issues de langue
        if not language.get("is_target_language", True):
            issues.append(f"Langue non cible ({language.get('language', 'unknown')})")
        elif language.get("confidence", 0) < self.min_language_confidence:
            issues.append(f"Langue incertaine (confiance: {language['confidence']:.2f})")
            
        # Issues de contenu
        if quality.get("has_urls", False) and quality.get("has_emails", False):
            issues.append("Contenu promotionnel suspect (URLs + emails)")
            
        return issues
    
    def score_dataset(self, document_scores: List[Dict], similarity_stats: Dict) -> Dict:
        """Score global du dataset (version stricte)"""
        if not document_scores:
            return {"overall_score": 0.0, "quality_distribution": {}}
            
        scores = [doc["scores"]["overall"] for doc in document_scores]
        instruction_count = sum(1 for doc in document_scores if doc["debug"].get("instruction_format", False))
        
        # Distribution avec seuils plus stricts
        excellent = sum(1 for s in scores if s >= 0.8)
        good = sum(1 for s in scores if 0.65 <= s < 0.8)
        average = sum(1 for s in scores if 0.45 <= s < 0.65)
        poor = sum(1 for s in scores if s < 0.45)
        
        base_score = np.mean(scores)
        
        # Bonus réduits et conditionnels
        diversity_bonus = similarity_stats.get("diversity_score", 0.5) * 0.03 if base_score > 0.5 else 0
        instruction_bonus = (instruction_count / len(document_scores)) * 0.05 if base_score > 0.6 else 0
        
        # Malus pour datasets de mauvaise qualité
        corruption_malus = 0
        if poor / len(document_scores) > 0.3:  # Plus de 30% de documents de mauvaise qualité
            corruption_malus = 0.2
        if poor / len(document_scores) > 0.5:  # Plus de 50% de documents de mauvaise qualité  
            corruption_malus = 0.4
            
        dataset_score = max(0.0, min(1.0, base_score + diversity_bonus + instruction_bonus - corruption_malus))
        
        return {
            "overall_score": dataset_score,
            "average_document_score": base_score,
            "diversity_bonus": diversity_bonus,
            "instruction_bonus": instruction_bonus,
            "corruption_malus": corruption_malus,
            "total_documents": len(document_scores),
            "instruction_documents": instruction_count,
            "quality_distribution": {
                "excellent": excellent,
                "good": good, 
                "average": average,
                "poor": poor
            },
            "recommendations": {
                "keep": excellent + good,
                "review": average,
                "reject": poor
            }
        }