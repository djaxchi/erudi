# Architecture

Erudi suit une architecture multi-engine avec détection automatique du backend (MLX, CUDA, CPU).

Les domaines principaux :
- `conversations/` - génération et streaming
- `llms/` — gestion du cycle de vie des modèles
- `knowledge_base/` - RAG avec FAISS
- `training/` - fine-tuning
- `hardware/` - monitoring

Chaque domaine est documenté via mkdocstrings :
- [Engines](reference/engines.md)
- [LLMs](reference/llms.md)
