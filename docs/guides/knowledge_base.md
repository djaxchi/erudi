# 📚 Guide — Knowledge Base

Guide pratique pour créer des bases de connaissances (RAG) et spécialiser des modèles.

## But

Le domaine **Knowledge Base** permet d'attacher des documents (PDF, TXT) à un modèle LLM pour :
- **RAG (Retrieval-Augmented Generation)** : Injection de contexte pertinent lors de la génération
- **Spécialisation** : Le modèle accède à des connaissances spécifiques (docs internes, code, etc.)
- **Réduction d'hallucinations** : Réponses fondées sur des documents fournis

## Architecture RAG

```
User Query
   ↓
Embed query (384 dims)
   ↓
FAISS similarity search → Top-K chunks
   ↓
Inject chunks in system prompt
   ↓
LLM generates with context
```

**Embedder** : `paraphrase-multilingual-MiniLM-L12-v2` (384 dimensions)  
**Index** : FAISS `IndexFlatL2` (exact search, L2 distance)  
**Chunking** : 384 tokens per chunk, 15% overlap

## Créer une Knowledge Base

### Upload Documents

```bash
curl -X POST http://127.0.0.1:8765/erudi/knowledge_base \
  -F "base_model_id=1" \
  -F "files=@docs/manual.pdf" \
  -F "files=@docs/faq.txt" \
  -F "files=@docs/code_examples.pdf"
```

**Formats supportés** :
- **PDF** : Extraction via pypdf (texte uniquement, pas d'OCR)
- **TXT** : Lecture directe avec encoding UTF-8

**Réponse** :

```json
{
  "kb_id": 1,
  "specialized_model_id": 35,
  "status": "processing",
  "message": "KB job created"
}
```

### Surveiller le Traitement

```bash
curl http://127.0.0.1:8765/erudi/knowledge_base/jobs/1
```

**Status possibles** :
- `pending` : En file d'attente
- `running` : Traitement en cours (extraction, embedding, indexation)
- `completed` : KB prête à l'emploi
- `failed` : Erreur (voir `error_message`)

### Temps de Traitement

**Dépend de** :
- Nombre de pages/documents
- Taille totale (chars)
- Performance CPU/GPU (embedding)

**Estimations** :
- 10 pages PDF : ~5-10 secondes
- 100 pages PDF : ~30-60 secondes
- 1000 pages PDF : ~5-10 minutes

## Utiliser un Modèle Spécialisé

### Créer une Conversation

```bash
curl -X POST http://127.0.0.1:8765/erudi/conversations \
  -H "Content-Type: application/json" \
  -d '{
    "llm_id": 35,
    "name": "Doc Q&A"
  }'
```

**Note** : `llm_id=35` est le modèle spécialisé (clone du base avec `kb_id` attaché).

### Poser des Questions

```bash
curl -X POST http://127.0.0.1:8765/erudi/conversations/42/generate \
  -H "Content-Type: application/json" \
  -d '{
    "content": "What is the installation procedure?"
  }'
```

Le système :
1. Embed la question
2. Cherche les top-K chunks pertinents dans FAISS
3. Injecte les chunks dans le system prompt
4. Génère la réponse avec contexte

**Top-K selon taille du modèle** :
- <2B : 1 chunk
- 2-16B : 1 chunk
- 16B+ : 3 chunks

Voir `backend/src/utils/prompt_utils.py::get_prompting_strategy()`.

## Supprimer une KB

```bash
curl -X DELETE http://127.0.0.1:8765/erudi/knowledge_base/1
```

Supprime :
- Le `KnowledgeBase`
- Le `VectorStore` (mapping ID → texte)
- L'index FAISS sur disque
- Le modèle spécialisé
- Les conversations associées (cascade)

**Attention** : Le modèle de base reste intact.

## Pipeline de Traitement

### 1. Extraction

**PDF** :
```python
from src.utils.file_processor import extract_text_from_pdf

text = extract_text_from_pdf("document.pdf")
# Retourne le texte brut de toutes les pages
```

**TXT** :
```python
with open("document.txt", "r", encoding="utf-8") as f:
    text = f.read()
```

### 2. Nettoyage

```python
from src.utils.file_processor import clean_text

cleaned = clean_text(raw_text)
# - Normalise Unicode (NFKD)
# - Supprime accents
# - Collapse whitespace
# - Filtre contrôle chars
# - ASCII only
```

### 3. Chunking

```python
from src.utils.file_processor import chunk_by_tokens

chunks = chunk_by_tokens(cleaned)
# - Target: 384 tokens per chunk (~1152 chars)
# - Overlap: 15% (~58 tokens)
# - Returns: List[str]
```

### 4. Embedding

```python
from src.utils.inference_utils import EmbedderService

embedder = EmbedderService.get_embedder()
embeddings = embedder.encode(chunks, convert_to_tensor=True)
# Shape: (n_chunks, 384)
```

### 5. Indexation FAISS

```python
import faiss
import numpy as np

# Create index
index = faiss.IndexFlatL2(384)

# Add vectors
embeddings_np = embeddings.cpu().numpy().astype('float32')
index.add(embeddings_np)

# Save to disk
faiss.write_index(index, "backend/data/indexes/1.index")
```

### 6. VectorStore

Stocke le mapping FAISS ID → texte :

```python
vectors_data = {
    "0": "First chunk text...",
    "1": "Second chunk text...",
    ...
}

vector_store = VectorStore(
    kb_id=1,
    vectors_data=json.dumps(vectors_data)
)
db.add(vector_store)
```

## Retrieval (Top-K)

### Embed Query

```python
query = "What is the installation procedure?"
query_embedding = embedder.encode([query])  # (1, 384)
```

### FAISS Search

```python
index = faiss.read_index("backend/data/indexes/1.index")
distances, indices = index.search(query_embedding, k=3)

# distances: array([[0.23, 0.45, 0.67]])
# indices: array([[42, 17, 89]])
```

### Retrieve Texts

```python
vector_store = db.query(VectorStore).filter(VectorStore.kb_id == 1).first()
vectors_data = json.loads(vector_store.vectors_data)

relevant_texts = [vectors_data[str(idx)] for idx in indices[0]]
```

### Inject in Prompt

```python
kb_context = "\n\n".join(relevant_texts)
system_prompt += f"\n\nRelevant context:\n{kb_context}"
```

Voir `backend/src/utils/kb_utils.py::get_relevant_texts_from_kb()`.

## Bonnes Pratiques

### Qualité des Documents

**Préférer** :
- PDFs avec texte sélectionnable (pas scannés)
- Textes structurés (sections, listes)
- Langage clair et concis

**Éviter** :
- PDFs scannés (nécessite OCR non supporté)
- Images, diagrammes (texte non extractible)
- Documents très longs sans structure (>1000 pages)

### Taille du KB

**Recommandations** :
- **Petits projets** : 10-50 documents (~500 KB)
- **Projets moyens** : 50-200 documents (~5 MB)
- **Grands projets** : 200-1000 documents (~50 MB)

**Limitations** :
- FAISS IndexFlatL2 : Pas de limite théorique
- Performance : ~50ms pour top-k=3 sur 10K chunks
- Disque : ~1.5 MB par 1000 chunks

### Chunking Strategy

**Default (384 tokens)** : Bon équilibre contexte/granularité

**Ajustements** :
- **Plus petit (256 tokens)** : Recherche plus précise, risque de fragmentation
- **Plus grand (512 tokens)** : Plus de contexte par chunk, moins précis

Modifier dans `backend/src/utils/file_processor.py::chunk_by_tokens()`.

### Top-K Selection

**Default (1-3 selon modèle)** : Évite surcharge du context window

**Ajustements** :
- **Augmenter** : Plus de contexte, risque de bruit
- **Réduire** : Moins de bruit, risque de manquer info

Modifier dans `backend/src/utils/prompt_utils.py::get_prompting_strategy()`.

## Debugging

### KB Vide ou Pas de Résultats

Vérifier :
```bash
# Nombre de chunks
curl http://127.0.0.1:8765/erudi/knowledge_base/1
# Retourne "file_names_list" et count

# Index FAISS
ls -lh backend/data/indexes/1.index
# Doit exister et avoir taille > 0
```

### Mauvaise Qualité de Retrieval

**Causes possibles** :
- Query trop vague ("help" vs "how to install on Mac")
- Documents mal structurés
- Top-K trop faible

**Solutions** :
- Reformuler la question avec mots-clés spécifiques
- Augmenter top-K temporairement
- Restructurer les documents source

### Performance Lente

**Embed query** : ~10-50ms (normal)  
**FAISS search** : ~10-50ms (normal)  
**Total retrieval** : <100ms

Si > 500ms :
- Vérifier CPU/GPU load
- Vérifier index size (>100K chunks = considérer HNSW)

## Exemples d'Utilisation

### Workflow Complet

```python
import requests
import time

base_url = 'http://127.0.0.1:8765/erudi'

# 1. Créer KB avec documents
files = [
    ('files', open('manual.pdf', 'rb')),
    ('files', open('faq.txt', 'rb'))
]
resp = requests.post(f'{base_url}/knowledge_base', 
                     data={'base_model_id': 1}, 
                     files=files)
kb_id = resp.json()['kb_id']
model_id = resp.json()['specialized_model_id']

# 2. Attendre traitement
while True:
    job = requests.get(f'{base_url}/knowledge_base/jobs/{kb_id}').json()
    if job['status'] == 'completed':
        break
    elif job['status'] == 'failed':
        raise Exception(job['error_message'])
    time.sleep(2)

# 3. Créer conversation avec modèle spécialisé
conv = requests.post(f'{base_url}/conversations', json={
    'llm_id': model_id,
    'name': 'Doc Q&A'
}).json()

# 4. Poser questions
resp = requests.post(f'{base_url}/conversations/{conv["id"]}/generate',
                     json={'content': 'How to install?'}, stream=True)
for chunk in resp.iter_content(decode_unicode=True):
    print(chunk, end='')
```

### Multi-document KB

```python
# Organiser par thème
kb_configs = [
    {
        'name': 'Product Docs',
        'files': ['docs/user_guide.pdf', 'docs/api_reference.pdf']
    },
    {
        'name': 'Internal Wiki',
        'files': ['wiki/processes.txt', 'wiki/faq.txt']
    }
]

for config in kb_configs:
    files = [('files', open(f, 'rb')) for f in config['files']]
    resp = requests.post(f'{base_url}/knowledge_base',
                         data={'base_model_id': 1},
                         files=files)
    print(f"Created KB: {config['name']}, ID: {resp.json()['kb_id']}")
```

## API Référence

Documentation complète des endpoints :

- [Knowledge Base Reference](../reference/knowledge_base.md)
- [Schemas Reference](../reference/knowledge_base.md#schemas)
- [Utils Reference](../reference/core.md) (kb_utils, file_processor)

## Voir Aussi

- [Guide Conversations](conversations.md) — Utiliser les modèles spécialisés
- [Guide LLMs](llms.md) — Charger les modèles de base
- [Architecture](../architecture.md) — RAG architecture détaillée
- [File Processor Reference](../reference/core.md) — Chunking et extraction
