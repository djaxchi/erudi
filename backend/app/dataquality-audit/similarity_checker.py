# similarity_checker.py
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from typing import List, Dict, Tuple
import logging

class SimilarityChecker:
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        model_name = config.get("similarity_model", "paraphrase-MiniLM-L6-v2")
        device = config.get("device", "cpu")
        try:
            self.model = SentenceTransformer(model_name, device=device)
            self.logger.info(f"Modèle de similarité chargé: {model_name} sur {device}")
        except Exception as e:
            self.logger.error(f"Erreur chargement modèle: {e}")
            self.model = None
    
    def find_duplicates(self, documents: List[Dict], threshold: float = None) -> List[Dict]:
        """Trouve les documents similaires/doublons"""
        if not self.model or len(documents) < 2:
            return []

        threshold = threshold or self.config.get("similarity_threshold", 0.85)
        valid_docs = []
        texts = []

        for doc in documents:
            if doc.get("issues", {}).get("too_short") or doc.get("issues", {}).get("has_replacement_chars") or not doc.get("language", {}).get("is_target_language", True):
                continue
            text = doc.get("text", "").strip()
            if text and len(text) > self.config.get("thresholds", {}).get("min_tokens", 50):
                if len(text) > 5000:
                    text = text[:2500] + "..." + text[-2500:]
                texts.append(text)
                valid_docs.append(doc)

        if len(texts) < 2:
            return []

        try:
            self.logger.info(f"Calcul des embeddings pour {len(texts)} documents...")
            embeddings = self.model.encode(texts, show_progress_bar=True, batch_size=self.config.get("batch_size", 32))

            # Utiliser faiss pour une recherche efficace
            import faiss
            index = faiss.IndexFlatIP(embeddings.shape[1])
            faiss.normalize_L2(embeddings)
            index.add(embeddings)

            distances, indices = index.search(embeddings, k=10)  # Top 10 voisins
            duplicates = []
            processed = set()

            for i in range(len(embeddings)):
                if i in processed:
                    continue
                similar_indices = [idx for idx, dist in zip(indices[i], distances[i]) if dist >= threshold and idx != i and idx not in processed]
                if similar_indices:
                    group = {
                        "main_document": valid_docs[i]["filename"],
                        "similar_documents": [valid_docs[idx]["filename"] for idx in similar_indices],
                        "similarities": [float(dist) for dist in distances[i] if dist >= threshold and indices[i][list(distances[i]).index(dist)] != i],
                        "group_size": len(similar_indices) + 1,
                        "has_instruction_format": valid_docs[i].get("instruction_format", False)
                    }
                    duplicates.append(group)
                    processed.add(i)
                    processed.update(similar_indices)

            self.logger.info(f"Trouvé {len(duplicates)} groupes de doublons")
            return duplicates

        except Exception as e:
            self.logger.error(f"Erreur calcul similarité: {e}")
            return []
        
    def get_similarity_stats(self, documents: List[Dict]) -> Dict:
        """Statistiques générales de similarité du corpus"""
        if not self.model or len(documents) < 2:
            return {"avg_similarity": 0.0, "max_similarity": 0.0, "diversity_score": 1.0, "cluster_count": 0}

        try:
            # Filtrer les documents valides
            valid_docs = [doc for doc in documents if not doc.get("issues", {}).get("too_short") and not doc.get("issues", {}).get("has_replacement_chars") and doc.get("language", {}).get("is_target_language", True)]
            if len(valid_docs) < 2:
                return {"avg_similarity": 0.0, "max_similarity": 0.0, "diversity_score": 1.0, "cluster_count": 0}

            # Échantillonnage stratifié
            sample_size = min(self.config.get("sample_size", 100), len(valid_docs))
            sampled_docs = self._stratified_sample(valid_docs, sample_size)

            texts = [doc.get("text", "")[:1000] for doc in sampled_docs if doc.get("text")]
            if len(texts) < 2:
                return {"avg_similarity": 0.0, "max_similarity": 0.0, "diversity_score": 1.0, "cluster_count": 0}

            embeddings = self.model.encode(texts, batch_size=self.config.get("batch_size", 32))
            similarity_matrix = cosine_similarity(embeddings)
            np.fill_diagonal(similarity_matrix, 0)

            # Clustering pour diversité
            from sklearn.cluster import KMeans
            n_clusters = min(10, len(texts))
            kmeans = KMeans(n_clusters=n_clusters, random_state=42).fit(embeddings)
            cluster_count = len(set(kmeans.labels_))

            avg_sim = np.mean(similarity_matrix)
            max_sim = np.max(similarity_matrix)
            diversity_score = 1.0 - avg_sim + (cluster_count / n_clusters) * 0.2

            return {
                "avg_similarity": float(avg_sim),
                "max_similarity": float(max_sim),
                "diversity_score": float(max(0.0, min(1.0, diversity_score))),
                "cluster_count": cluster_count
            }

        except Exception as e:
            self.logger.error(f"Erreur stats similarité: {e}")
            return {"avg_similarity": 0.0, "max_similarity": 0.0, "diversity_score": 1.0, "cluster_count": 0}

    def _stratified_sample(self, documents: List[Dict], sample_size: int) -> List[Dict]:
        """Échantillonnage stratifié par type de contenu et langue"""
        from collections import defaultdict
        import random

        # Grouper par type de contenu et langue
        groups = defaultdict(list)
        for doc in documents:
            key = (doc["content_type"].get("dominant_type", "generic"), doc["language"].get("language", "unknown"))
            groups[key].append(doc)

        sampled_docs = []
        total_docs = len(documents)
        for group, docs in groups.items():
            group_size = int(sample_size * (len(docs) / total_docs))
            sampled_docs.extend(random.sample(docs, min(group_size, len(docs))))

        # Compléter si nécessaire
        if len(sampled_docs) < sample_size:
            remaining = random.sample(documents, min(sample_size - len(sampled_docs), len(documents)))
            sampled_docs.extend(remaining)

        return sampled_docs[:sample_size]