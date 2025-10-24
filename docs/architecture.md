# 🧩 Architecture

Documentation de l'architecture technique d'Erudi : structure DDD, multi-engine, patterns et flux.

## Vue d'Ensemble

Erudi suit une **architecture hexagonale** avec séparation claire entre domaines métier, infrastructure et adapters. Le backend FastAPI utilise un **Domain-Driven Design (DDD)** organisé par domaines.

```
┌─────────────────────────────────────────────────────────────────┐
│ Frontend (Electron + React + Tailwind)                         │
│  - Contexts: LLM, Conversation, KB                             │
│  - Services: API client (REST)                                 │
└────────────────┬────────────────────────────────────────────────┘
                 │ REST API (JSON)
┌────────────────▼────────────────────────────────────────────────┐
│ Backend FastAPI                                                 │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ API Layer (endpoints/)                                      │ │
│ │  - Route handlers, Pydantic schemas, DI                     │ │
│ └────────────────┬────────────────────────────────────────────┘ │
│ ┌────────────────▼────────────────────────────────────────────┐ │
│ │ Service Layer (services/)                                   │ │
│ │  - Business logic, orchestration                            │ │
│ └────────────────┬────────────────────────────────────────────┘ │
│ ┌────────────────▼────────────────────────────────────────────┐ │
│ │ Repository Layer (repository/)                              │ │
│ │  - Data access, queries                                     │ │
│ └────────────────┬────────────────────────────────────────────┘ │
│ ┌────────────────▼────────────────────────────────────────────┐ │
│ │ Entity Layer (entities/)                                    │ │
│ │  - SQLAlchemy models, validators                            │ │
│ └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│ Infrastructure                                                  │
│  - Engines: MLX / CUDA / CPU (BaseEngine abstraction)          │
│  - Database: SQLite + SQLAlchemy ORM                           │
│  - Utils: RAG (FAISS), embeddings, prompting                   │
└─────────────────────────────────────────────────────────────────┘
```

## Domaines Principaux

### 1. Conversations
- **Responsabilité** : Gestion des sessions de chat et streaming
- **Endpoints** : POST `/conversations`, GET, DELETE, streaming
- **Entities** : `Conversation`, `Message`
- **Features** : Multi-tier memory (short/middle/long-term + KB), paramètres (temperature, top_p)
- [Référence complète](reference/conversations.md)

### 2. LLMs
- **Responsabilité** : Cycle de vie des modèles (download, load, unload, cleanup)
- **Endpoints** : GET `/llms`, POST download, DELETE
- **Entities** : `Llm`, `DownloadJob`
- **Features** : HuggingFace integration, quantization MLX, attachement KB
- [Référence complète](reference/llms.md)

### 3. Knowledge Base
- **Responsabilité** : RAG via FAISS vectorization
- **Endpoints** : POST `/knowledge_base`, GET status
- **Entities** : `KnowledgeBase`, `VectorStore`, `KBJob`
- **Features** : PDF/TXT processing, chunking, embedding, top-k retrieval
- [Référence complète](reference/knowledge_base.md)

### 4. Arena
- **Responsabilité** : Comparaison côte-à-côte de modèles
- **Endpoints** : POST `/arena/compare` (streaming)
- **Features** : Génération parallèle, streaming synchronisé
- [Référence complète](reference/arena.md)

### 5. Hardware
- **Responsabilité** : Monitoring système et scoring de performance
- **Endpoints** : GET `/hardware/static`, `/dynamic`, `/training`
- **Entities** : `StaticHardwareInfos`
- **Features** : Détection Apple Silicon, scoring GPU/CPU, estimations de perf
- [Référence complète](reference/hardware.md)

### 6. Training
- **Responsabilité** : Fine-tuning causal LM (future feature, stub actuel)
- **Entities** : `TrainingJob`
- **Status** : En développement
- [Référence complète](reference/training.md)

## Architecture Multi-Engine

### Pattern Strategy

Erudi utilise le pattern **Strategy** pour supporter plusieurs backends d'inférence :

```python
# backend/src/engines/base_engine.py
class BaseEngine(ABC):
    @classmethod
    def get_engine(cls) -> BaseEngine:
        """Auto-select engine based on hardware."""
        if MLX_Engine.is_available():
            return MLX_Engine()
        elif CUDA_Engine.is_available():
            return CUDA_Engine()
        else:
            return CPU_Engine()
    
    @abstractmethod
    async def generate_stream(self, prompt, params):
        """Unified interface for all engines."""
        pass
```

### Engines Disponibles

| Engine | Platform | Accélération | Status |
|--------|----------|--------------|--------|
| **MLX_Engine** | Mac Silicon (M1/M2/M3) | Apple Neural Engine + GPU | ✅ Production |
| **CUDA_Engine** | Linux/Windows + NVIDIA | CUDA + cuDNN | 🚧 Stub |
| **CPU_Engine** | Toutes plateformes | CPU only (lent) | 🚧 Stub |

### Sélection Automatique

Au démarrage (`lifespan`), l'engine est auto-sélectionné :
1. **MLX** si Apple Silicon détecté (`platform.processor() == 'arm'`)
2. **CUDA** si GPU NVIDIA détecté (`torch.cuda.is_available()`)
3. **CPU** en fallback

Voir [Engines Reference](reference/engines.md) pour détails d'implémentation.

## Flux de Démarrage (Lifespan)

```python
# backend/src/core/api.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Sélection de l'engine
    config.LLM_Engine = BaseEngine.get_engine()
    
    # 2. Création des tables SQLite
    createTables()
    
    # 3. Seed de la base (HuggingFace models)
    startup_populate_database()
    
    # 4. Démarrage du cleanup task (30s interval)
    cleanup_task = asyncio.create_task(cleanup_loop())
    
    yield  # Application running
    
    # 5. Cleanup à l'arrêt
    cleanup_task.cancel()
```

Ordre d'exécution :
1. **Engine selection** → `config.LLM_Engine` global
2. **Database init** → Tables créées si absentes
3. **Seed** → Modèles HF populaires ajoutés (Mistral, Gemma, Qwen)
4. **Cleanup loop** → Décharge modèles inactifs toutes les 30s
5. **Yield** → Application prête
6. **Shutdown** → Cancel cleanup task

## Conventions de Code

### Naming
- **snake_case** : variables, fonctions, fichiers, directories
- **Capitalized_Snake_Case** : classes
- **UPPER_SNAKE_CASE** : constantes
- **Imports absolus** : toujours `from src.core.config import ...`

### Structure de Domaine

Chaque domaine suit cette structure :

```
backend/src/domains/<domain>/
├── __init__.py
├── endpoints.py      # FastAPI routes (API layer)
├── schemas.py        # Pydantic models (validation)
├── services.py       # Business logic
└── repository.py     # Data access (optionnel)
```

Pattern de flux :
```
HTTP Request
   ↓
endpoints.py (validation Pydantic)
   ↓
services.py (business logic)
   ↓
repository.py (DB queries)
   ↓
entities/*.py (SQLAlchemy models)
```

### Gestion des Erreurs

Hiérarchie d'exceptions applicatives :

```python
# backend/src/core/exceptions.py
class AppBaseException(Exception):
    """Base pour toutes les exceptions Erudi."""
    
class ModelNotFoundError(AppBaseException):
    """Modèle LLM introuvable."""
    
class InferenceError(AppBaseException):
    """Erreur durant la génération."""
```

Handler global dans `api.py` :

```python
@app.exception_handler(AppBaseException)
async def app_base_exception_handler(req, exc):
    return JSONResponse(
        status_code=400,
        content={"error": str(exc)}
    )
```

### Logging Structuré

```python
from src.core.logging import logger

logger.info("Model loaded", extra={
    "llm_id": 42,
    "model_name": "mistral-7b",
    "engine": "mlx"
})
```

Format : `[TIMESTAMP] [LEVEL] [MODULE] Message {context}`

Logs écrits dans `backend/logs/app.log`.

## Persistence (SQLite + SQLAlchemy)

### Modèles Principaux

- **Llm** : Catalogue de modèles (name, link, local, quantized, kb_id)
- **Conversation** : Sessions de chat (llm_id, temperature, top_p, max_tokens)
- **Message** : Messages individuels (conversation_id, sender, content, starred)
- **KnowledgeBase** : Métadonnées KB (index_path, file_names_list)
- **VectorStore** : Mapping FAISS ID → texte (vectors_data JSON)
- **DownloadJob** : Jobs de téléchargement (status, progress, total_bytes)
- **StaticHardwareInfos** : Profil matériel (singleton)

Voir [Entities Reference](reference/entities.md) pour schémas complets.

### Repository Pattern

```python
# backend/src/domains/llms/repository.py (example)
def get_llm_by_id(db: Session, llm_id: int) -> Optional[Llm]:
    return db.query(Llm).filter(Llm.id == llm_id).first()
```

Accès DB via dependency injection :

```python
@router.get("/llms/{llm_id}")
def get_llm(llm_id: int, db: Session = Depends(get_db)):
    llm = get_llm_by_id(db, llm_id)
    if not llm:
        raise ModelNotFoundError(f"LLM {llm_id} not found")
    return llm
```

## RAG (Retrieval-Augmented Generation)

### Architecture FAISS

1. **Embedder** : `paraphrase-multilingual-MiniLM-L12-v2` (384 dims)
2. **Chunking** : Token-aware (384 tokens, 15% overlap)
3. **Index** : FAISS `IndexFlatL2` (L2 distance)
4. **Storage** : `VectorStore.vectors_data` JSON mapping ID → texte

### Flux de Création KB

```
PDF/TXT files
   ↓
file_processor.prepare_for_knowledge_base()  # Extract + clean
   ↓
chunk_by_tokens()  # 384 tokens per chunk
   ↓
EmbedderService.get_embedder().encode()  # Generate embeddings
   ↓
faiss.IndexFlatL2()  # Build index
   ↓
VectorStore (save mapping)
   ↓
KnowledgeBase (save metadata)
```

### Injection dans Prompt

```python
# backend/src/utils/kb_utils.py
def get_relevant_texts_from_kb(query, llm, db, kb_top_k=3):
    # 1. Embed query
    embedder = EmbedderService.get_embedder()
    query_embedding = embedder.encode([query])
    
    # 2. FAISS search
    index = faiss.read_index(kb.index_path)
    distances, indices = index.search(query_embedding, kb_top_k)
    
    # 3. Retrieve texts
    vector_store = db.query(VectorStore).filter(...).first()
    texts = [vector_store.vectors_data[str(idx)] for idx in indices[0]]
    
    return texts
```

Voir [Knowledge Base Guide](guides/knowledge_base.md) et [KB Reference](reference/knowledge_base.md).

## Prompting Multi-Tier Memory

### Stratégie par Taille de Modèle

| Size | Short-term | Middle-term (vector) | Long-term (summary) | KB top-k |
|------|------------|----------------------|---------------------|----------|
| <2B (tiny) | 2 turns | 1 chunk | ❌ | 1 |
| 2-4B (small) | 3 turns | ❌ | ❌ | 1 |
| 4-8B (medium) | 3 turns | 1 chunk | ✅ | 1 |
| 8-16B (large) | 3 turns | 1 chunk | ✅ | 1 |
| 16B+ (xlarge) | 5 turns | 2 chunks | ✅ | 3 |

Implémentation : `backend/src/utils/prompt_utils.py`

Voir [Prompt Utils Reference](reference/core.md).

## Performance et Optimisations

### Model Cleanup Loop

Task background qui décharge les modèles inactifs :

```python
async def cleanup_loop():
    while True:
        await asyncio.sleep(30)  # Every 30s
        if config.LLM_Engine.is_loaded():
            inactive_time = datetime.now() - last_generation_time
            if inactive_time > timedelta(minutes=5):
                config.LLM_Engine.unload_model()
```

### Streaming Response

```python
async def generate_stream():
    for token in engine.generate_stream(prompt, params):
        yield token
        
return StreamingResponse(generate_stream(), media_type="text/plain")
```

Évite le buffering et réduit la latence perçue.

### FAISS Index Optimization

- **IndexFlatL2** : Exact search, pas d'approximation
- **Performance** : ~10-50ms pour top-k=3 sur 1000 chunks
- **Memory** : ~1.5 MB par 1000 chunks (384 dims, fp32)

## Références Rapides

- [Core Reference](reference/core.md) — Config, logging, exceptions
- [Engines Reference](reference/engines.md) — MLX, CUDA, CPU
- [Conversations Reference](reference/conversations.md) — Chat endpoints
- [LLMs Reference](reference/llms.md) — Model management
- [KB Reference](reference/knowledge_base.md) — RAG
- [Entities Reference](reference/entities.md) — SQLAlchemy models

## Diagrammes Supplémentaires

### Flux de Génération Streaming

```
User → POST /conversations/{id}/generate
  ↓
endpoints.generate_message_stream()
  ↓
services.prepare_prompt() → Multi-tier memory injection
  ↓
engine.generate_stream(prompt, params)
  ↓
yield token → StreamingResponse
  ↓
User receives tokens in real-time
```

### Flux de Téléchargement + Quantization

```
User → POST /llms/download {remote_model_id, quantize}
  ↓
Create DownloadJob (status=pending)
  ↓
Background task starts
  ↓
Download from HuggingFace → Update progress
  ↓
If quantize: MLX_Engine.quant_and_save_from_hf_format()
  ↓
Create Llm entry (local=1)
  ↓
DownloadJob status=completed
```

Voir [LLMs Guide](guides/llms.md) pour utilisation pratique.

