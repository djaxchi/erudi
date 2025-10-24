# 🧠 Erudi Documentation

Bienvenue dans la documentation technique d'Erudi — une application desktop pour l'inférence locale de LLMs open-source avec spécialisation et RAG.

## 🎯 Vue d'Ensemble

Erudi permet de :
- **Exécuter des LLMs localement** sur Mac Silicon (MLX), NVIDIA GPU (CUDA), ou CPU
- **Spécialiser les modèles** via attachement de bases de connaissances (RAG)
- **Comparer des modèles** en mode Arena
- **Gérer le cycle de vie** : téléchargement, quantization, déchargement

## 📚 Sections

### Démarrage
- [🚀 Getting Started](usage.md) — Installation, lancement backend/frontend, premiers tests

### Concepts
- [🧩 Architecture](architecture.md) — Structure DDD, multi-engine, flux de démarrage

### Guides Pratiques
- [💬 Conversations](guides/conversations.md) — Créer des sessions, streaming, paramètres
- [🤖 LLMs](guides/llms.md) — Télécharger, charger, gérer les modèles
- [📚 Knowledge Base](guides/knowledge_base.md) — Créer des KB, attacher à un modèle

### Référence API
- [Core](reference/core.md) — Configuration, logging, santé
- [Engines](reference/engines.md) — MLX, CUDA, CPU
- [Conversations](reference/conversations.md) — Endpoints de chat
- [LLMs](reference/llms.md) — Gestion des modèles
- [Knowledge Base](reference/knowledge_base.md) — RAG et vectorisation
- [Arena](reference/arena.md) — Comparaison de modèles
- [Hardware](reference/hardware.md) — Monitoring système
- [Entities](reference/entities.md) — Modèles SQLAlchemy
- [Database](reference/database.md) — Seed et accès DB

## 🏗️ Architecture Rapide

```
┌─────────────────────────────────────────────────────────┐
│ Frontend (Electron + React)                             │
└────────────────┬────────────────────────────────────────┘
                 │ REST API
┌────────────────▼────────────────────────────────────────┐
│ Backend (FastAPI)                                       │
│  ├─ Domains: conversations, llms, KB, arena, hardware  │
│  ├─ Engines: MLX_Engine / CUDA_Engine / CPU_Engine     │
│  ├─ Database: SQLite + SQLAlchemy ORM                   │
│  └─ Utils: RAG (FAISS), prompting, embeddings          │
└─────────────────────────────────────────────────────────┘
```

## 🚦 Démarrage Rapide

```bash
# Backend
cd backend
source venv/bin/activate  # Mac/Linux
uvicorn src.main:app --reload

# Frontend
npm start
```

Voir [Usage](usage.md) pour les détails.

## 🔗 Liens Utiles

- [GitHub Repository](https://github.com/djaxchi/erudi)
- [Architecture détaillée](architecture.md)
- [API Reference complète](reference/core.md)

