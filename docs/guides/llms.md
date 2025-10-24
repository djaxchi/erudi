# 🤖 Guide — LLMs

Guide pratique pour gérer le cycle de vie des modèles : télécharger, charger, décharger, cleanup.

## But

Le domaine **LLMs** gère le catalogue de modèles et leurs opérations :
- Téléchargement depuis HuggingFace avec quantization optionnelle
- Chargement/déchargement en mémoire (VRAM/RAM)
- Attachement de Knowledge Bases pour RAG
- Monitoring des jobs de téléchargement

## Catalogue de Modèles

### Lister les Modèles Disponibles

```bash
curl http://localhost:8000/erudi/llms
```

Retourne tous les modèles (remote et local) :

```json
[
  {
    "id": 1,
    "name": "Mistral 7B Instruct v0.3",
    "link": "mistralai/Mistral-7B-Instruct-v0.3",
    "local": 0,  // 0=remote, 1=local, 2=downloading
    "type": "mistral",
    "quantized": 0,  // 0=not quantized, 1=pre-quantized
    "is_attached_to_kb": false,
    "kb_id": null
  }
]
```

### Rechercher un Modèle

```bash
curl http://localhost:8000/erudi/llms/search?query=gemma
```

Filtre par nom (case-insensitive).

## Téléchargement

### Télécharger et Quantizer (MLX)

```bash
curl -X POST http://localhost:8000/erudi/llms/download \
  -H "Content-Type: application/json" \
  -d '{
    "remote_model_id": "mistralai/Mistral-7B-Instruct-v0.3",
    "quantize": true,
    "quantize_type": "q4"
  }'
```

Réponse :

```json
{
  "job_id": 1,
  "remote_model_id": "mistralai/Mistral-7B-Instruct-v0.3",
  "status": "pending",
  "progress": 0.0,
  "total_bytes": 0,
  "created_at": "2025-10-25T12:00:00Z"
}
```

**Types de quantization MLX** :
- `q4` : 4-bit (recommandé, ~3-4 GB pour 7B)
- `q8` : 8-bit (~6-7 GB pour 7B)

### Surveiller le Téléchargement

```bash
curl http://localhost:8000/erudi/llms/download/1
```

Réponse en cours :

```json
{
  "job_id": 1,
  "status": "running",
  "progress": 45.2,
  "total_bytes": 13500000000,
  "time_left": 120,  // secondes
  "updated_at": "2025-10-25T12:05:00Z"
}
```

**Status possibles** :
- `pending` : En file d'attente
- `running` : Téléchargement en cours
- `completed` : Terminé avec succès
- `failed` : Erreur (voir `error_message`)
- `cancelled` : Annulé par l'utilisateur

### Annuler un Téléchargement

```bash
curl -X POST http://localhost:8000/erudi/llms/download/1/cancel
```

## Gestion de la Mémoire

### Charger un Modèle

Le chargement est **automatique** lors de la première génération. Pas besoin d'endpoint explicite.

### Vérifier le Statut

```bash
curl http://localhost:8000/erudi/hardware/static
```

Retourne :
- `loaded_model_id` : ID du modèle chargé (ou `null`)
- `available_ram_gb` : RAM disponible
- `available_vram_gb` : VRAM disponible (GPU/unified)

### Décharger un Modèle

```bash
curl -X POST http://localhost:8000/erudi/llms/unload
```

Libère immédiatement la mémoire (VRAM/RAM).

### Cleanup Automatique

Un **background task** décharge automatiquement les modèles inactifs :
- **Intervalle** : Toutes les 30 secondes
- **Seuil** : 5 minutes d'inactivité
- **Trigger** : Dernière génération > 5 min

Voir `backend/src/core/api.py::cleanup_loop()`.

## Supprimer un Modèle

```bash
curl -X DELETE http://localhost:8000/erudi/llms/1
```

Supprime :
- L'entrée DB
- Les fichiers sur disque (`backend/data/models/{id}/`)
- Les conversations associées (cascade)
- Le KB attaché (si existe)

**Attention** : Irréversible !

## Paramètres de Quantization

### MLX (Apple Silicon)

#### Q4 (4-bit)
- **Taille** : ~25% du modèle original
- **Qualité** : Légère perte (~2% perplexity)
- **Vitesse** : 20-30 tokens/s sur M2
- **Recommandé pour** : 7B models, usage général

#### Q8 (8-bit)
- **Taille** : ~50% du modèle original
- **Qualité** : Perte minime (~0.5% perplexity)
- **Vitesse** : 15-25 tokens/s sur M2
- **Recommandé pour** : Tasks critiques, grands context windows

### CUDA (NVIDIA)

**Status** : Stub (non implémenté)

Futur support :
- BitsAndBytes 4-bit/8-bit
- GPTQ
- AWQ

### CPU

**Status** : Stub (non implémenté)

Futur support :
- GGUF quantization (llama.cpp)

## Attachement Knowledge Base

Voir [Guide Knowledge Base](knowledge_base.md) pour créer un KB.

### Attacher un KB à un Modèle

Effectué automatiquement lors de la création du KB :

```bash
curl -X POST http://localhost:8000/erudi/knowledge_base \
  -F "base_model_id=1" \
  -F "files=@document.pdf"
```

Crée :
1. Un nouveau modèle spécialisé (clone du base)
2. Un `KnowledgeBase` lié
3. Attache `is_attached_to_kb=true`, `kb_id=X`

### Détacher un KB

```bash
curl -X DELETE http://localhost:8000/erudi/knowledge_base/{kb_id}
```

Supprime le KB et reset le modèle.

## Bonnes Pratiques

### Choix de Modèle par Use Case

| Use Case | Modèle Recommandé | Quantization | RAM Requis |
|----------|-------------------|--------------|------------|
| Chat général | Mistral 7B Instruct | Q4 | 8 GB |
| Code | Qwen 2.5 Coder 7B | Q4 | 8 GB |
| Créatif | Gemma 2 9B | Q8 | 16 GB |
| Multilingual | Qwen 2.5 7B | Q4 | 8 GB |
| Analyse | Gemma 2 27B | Q4 | 24 GB |

### Gestion VRAM/RAM

**Mac Silicon (unified memory)** :
- 8 GB RAM : Modèles jusqu'à 3B (Q4)
- 16 GB RAM : Modèles jusqu'à 7B (Q4) ou 4B (Q8)
- 24 GB RAM : Modèles jusqu'à 13B (Q4) ou 7B (Q8)
- 32 GB+ RAM : Modèles jusqu'à 27B (Q4)

**NVIDIA GPU** :
- 8 GB VRAM : Modèles jusqu'à 7B (Q4)
- 12 GB VRAM : Modèles jusqu'à 13B (Q4)
- 24 GB VRAM : Modèles jusqu'à 34B (Q4)

### Performance Téléchargement

**Facteurs** :
- Connexion internet (HuggingFace CDN)
- Taille du modèle (3-15 GB pour 7B models)
- Quantization (ajout 30-60s pour MLX)

**Temps typiques (100 Mbps)** :
- Mistral 7B (13.5 GB) : ~20 min download + 1 min quant
- Gemma 2B (5.5 GB) : ~8 min download + 30s quant

### Debugging

#### Téléchargement Échoué

Consulter `error_message` du DownloadJob :

```bash
curl http://localhost:8000/erudi/llms/download/1 | jq .error_message
```

**Erreurs courantes** :
- `Model not found on HuggingFace` : ID incorrect
- `Insufficient disk space` : Besoin 2x la taille du modèle
- `Timeout` : Connexion instable

#### Modèle ne Charge Pas

Vérifier les logs :

```bash
tail -f backend/logs/app.log | grep "load_model"
```

**Erreurs courantes** :
- `OOM (Out of Memory)` : RAM/VRAM insuffisant
- `Model files corrupted` : Re-télécharger
- `Engine not available` : MLX pas installé / GPU pas détecté

## Exemples d'Utilisation

### Workflow Complet

```python
import requests
import time

base_url = 'http://localhost:8000/erudi'

# 1. Télécharger et quantizer Mistral 7B
resp = requests.post(f'{base_url}/llms/download', json={
    'remote_model_id': 'mistralai/Mistral-7B-Instruct-v0.3',
    'quantize': True,
    'quantize_type': 'q4'
})
job_id = resp.json()['job_id']

# 2. Attendre la fin
while True:
    job = requests.get(f'{base_url}/llms/download/{job_id}').json()
    if job['status'] == 'completed':
        model_id = job['local_model_id']
        break
    elif job['status'] == 'failed':
        raise Exception(job['error_message'])
    print(f"Progress: {job['progress']:.1f}%")
    time.sleep(5)

# 3. Créer une conversation
conv = requests.post(f'{base_url}/conversations', json={
    'llm_id': model_id,
    'name': 'Test Chat'
}).json()

# 4. Générer
resp = requests.post(f'{base_url}/conversations/{conv["id"]}/generate',
                     json={'content': 'Hello!'}, stream=True)
for chunk in resp.iter_content(decode_unicode=True):
    print(chunk, end='')
```

### Comparer Plusieurs Modèles

```python
# Télécharger 2 modèles
models = ['mistralai/Mistral-7B-Instruct-v0.3', 'google/gemma-2-2b-it']
model_ids = []

for model_hf_id in models:
    resp = requests.post(f'{base_url}/llms/download', json={
        'remote_model_id': model_hf_id,
        'quantize': True
    })
    # Attendre download...
    model_ids.append(downloaded_model_id)

# Utiliser Arena pour comparer
resp = requests.post(f'{base_url}/arena/compare', json={
    'llm_ids': model_ids,
    'prompt': 'Explain quantum computing'
}, stream=True)
```

Voir [Guide Arena](arena.md) (à créer) pour détails.

## API Référence

Documentation complète des endpoints :

- [LLMs Reference](../reference/llms.md)
- [Download Jobs Reference](../reference/llms.md#downloadjobresponse)
- [Services Reference](../reference/llms.md#services)

## Voir Aussi

- [Guide Conversations](conversations.md) — Utiliser les modèles
- [Guide Knowledge Base](knowledge_base.md) — Spécialiser avec RAG
- [Hardware Reference](../reference/hardware.md) — Monitoring VRAM/RAM
- [Architecture](../architecture.md) — Multi-engine design
