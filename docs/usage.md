# 🚀 Getting Started

Guide de démarrage rapide pour installer et lancer Erudi localement.

## Prérequis

### Système d'exploitation
- **macOS** (Apple Silicon M1/M2/M3 recommandé pour MLX)
- **Linux** (avec NVIDIA GPU pour CUDA)
- **Windows** (avec NVIDIA GPU pour CUDA)

### Logiciels requis
- **Python 3.12.3+**
- **Node.js 18+** (pour le frontend)
- **Git**

### Matériel recommandé
- **Mac Silicon** : M1/M2/M3 avec 16+ GB RAM unifié
- **NVIDIA GPU** : RTX 3060+ avec 8+ GB VRAM
- **CPU uniquement** : 16+ GB RAM (mode fallback, plus lent)

## Installation

### 1. Cloner le repository

```bash
git clone https://github.com/djaxchi/erudi.git
cd erudi
```

### 2. Setup Backend

#### Mac Silicon (MLX)

```bash
cd backend
bash setup-mac-silicon.sh
```

Ce script crée un `venv` et installe les dépendances MLX depuis `requirements/entrypoints/dev/mac-silicon.txt`.

#### Linux CUDA 12.1

```bash
cd backend
bash setup-linux-cuda-121.sh
```

#### Windows CUDA 12.1

```powershell
cd backend
.\setup-win-cuda-121.ps1
```

### 3. Setup Frontend

```bash
cd frontend
npm install
```

## Lancement

### Backend (API FastAPI)

```bash
cd backend
source venv/bin/activate  # Mac/Linux
# ou
venv\Scripts\activate  # Windows

python run.py            # production-faithful launcher (JSON lifecycle events)
# OR for API-only iteration:
PYTHONPATH=. uvicorn src.main:app --reload --port 27182
```

Le backend démarre sur **http://127.0.0.1:27182** (cf `backend/run.py:72` —
le port défaut est 27182, scan jusqu'à 27199 si occupé).

### Frontend (Electron)

```bash
cd frontend
npm start
```

L'application desktop Electron s'ouvre automatiquement.

## Premiers Tests

### Health Check

Vérifier que le backend répond :

```bash
curl http://127.0.0.1:27182/erudi/health
```

Réponse attendue :

```json
{
  "status": "healthy",
  "engine": "mlx",  # ou "cuda" ou "cpu"
  "timestamp": "2025-10-25T..."
}
```

### Lister les modèles disponibles

```bash
curl http://127.0.0.1:27182/erudi/llms
```

Retourne les modèles seed depuis HuggingFace (Mistral, Gemma, etc.).

### Créer une conversation

```bash
curl -X POST http://127.0.0.1:27182/erudi/conversations \
  -H "Content-Type: application/json" \
  -d '{"llm_id": 1, "name": "Test Chat"}'
```

Retourne un objet `Conversation` avec `id`, `llm_id`, `name`, etc.

## Structure des Fichiers

```
erudi/
├── backend/
│   ├── src/             # Code source
│   │   ├── core/        # Config, logging, exceptions
│   │   ├── domains/     # Business logic (conversations, llms, etc.)
│   │   ├── engines/     # MLX/CUDA/CPU
│   │   ├── entities/    # SQLAlchemy models
│   │   └── utils/       # RAG, prompts, embeddings
│   ├── data/            # SQLite DB, models, cache
│   ├── logs/            # Application logs
│   └── requirements/    # Platform-specific deps
├── frontend/
│   └── src/             # React components
└── docs/                # Cette documentation
```

## Prochaines Étapes

- [Architecture](architecture.md) — Comprendre la structure du code
- [Guide Conversations](guides/conversations.md) — Utiliser l'API de chat
- [Guide LLMs](guides/llms.md) — Télécharger et gérer des modèles
- [API Reference](reference/conversations.md) — Documentation complète des endpoints

## Dépannage

### Le backend ne démarre pas

1. Vérifier que le venv est activé : `which python` doit pointer vers `backend/venv/bin/python`
2. Réinstaller les dépendances : `pip install -r requirements/entrypoints/dev/<platform>.txt`
3. Consulter les logs : `backend/logs/app.log`

### Erreur "No module named 'src'"

Le backend doit être lancé depuis le dossier `backend/` avec le venv activé.

### Erreur "Engine not available"

- **MLX** : Uniquement sur Mac Silicon. Vérifiez `platform.processor() == 'arm'`
- **CUDA** : Vérifiez `nvidia-smi` et PyTorch CUDA : `torch.cuda.is_available()`
- **Fallback CPU** : Toujours disponible mais plus lent

Voir [Hardware Reference](reference/hardware.md) pour diagnostics détaillés.
