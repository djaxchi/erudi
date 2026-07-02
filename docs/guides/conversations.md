# 💬 Guide — Conversations

Guide pratique pour utiliser l'API Conversations : créer des sessions, streamer des réponses, gérer les paramètres.

## But

Le domaine **Conversations** gère les sessions de chat interactives avec les LLMs. Chaque conversation :
- Appartient à un modèle LLM spécifique
- Maintient un historique de messages (user/llm)
- Stocke des paramètres de génération (temperature, top_p, max_tokens)
- Supporte le multi-tier memory (short/middle/long-term + KB)

## Principales Opérations

### 1. Créer une Conversation

```bash
curl -X POST http://127.0.0.1:27182/erudi/conversations \
  -H "Content-Type: application/json" \
  -d '{
    "llm_id": 1,
    "name": "Debug Session",
    "temperature": 0.7,
    "top_p": 0.95,
    "max_tokens": 1024
  }'
```

Réponse :

```json
{
  "id": 42,
  "llm_id": 1,
  "name": "Debug Session",
  "temperature": 0.7,
  "top_p": 0.95,
  "max_tokens": 1024,
  "created_at": "2025-10-25T12:00:00Z",
  "updated_at": "2025-10-25T12:00:00Z"
}
```

### 2. Générer une Réponse (Streaming)

```bash
curl -X POST http://127.0.0.1:27182/erudi/conversations/42/generate \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Explain async/await in Python"
  }'
```

Le serveur retourne un **stream de tokens** :

```
Async/await ... is ... a ... syntax ... for ... writing ... asynchronous ... code...
```

**Implémentation côté client (JavaScript)** :

```javascript
const response = await fetch('/erudi/conversations/42/generate', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({content: 'Explain async/await in Python'})
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const {done, value} = await reader.read();
  if (done) break;
  
  const token = decoder.decode(value);
  console.log(token);  // Display token in real-time
}
```

### 3. Récupérer l'Historique

```bash
curl http://127.0.0.1:27182/erudi/conversations/42
```

Retourne la conversation avec tous les messages :

```json
{
  "id": 42,
  "llm_id": 1,
  "name": "Debug Session",
  "messages": [
    {"id": 1, "sender": "user", "content": "Explain async/await..."},
    {"id": 2, "sender": "llm", "content": "Async/await is a syntax..."}
  ]
}
```

### 4. Lister Toutes les Conversations

```bash
curl http://127.0.0.1:27182/erudi/conversations
```

### 5. Supprimer une Conversation

```bash
curl -X DELETE http://127.0.0.1:27182/erudi/conversations/42
```

Supprime la conversation et tous ses messages (cascade).

### 6. Starring des Messages

Marquer un message comme important (pour injection dans system prompt) :

```bash
curl -X POST http://127.0.0.1:27182/erudi/conversations/42/messages/1/star
```

Unstar :

```bash
curl -X POST http://127.0.0.1:27182/erudi/conversations/42/messages/1/unstar
```

Les messages starred sont injectés dans le system prompt pour guider le comportement du modèle.

## Paramètres de Génération

### Temperature

**Range** : 0.0 - 2.0

- **0.0** : Déterministe, toujours le token le plus probable
- **0.7** : Équilibré (défaut recommandé)
- **1.0** : Sampling standard
- **1.5+** : Créatif, risque d'incohérence

**Recommandations** :
- Code/Factuel : 0.2 - 0.5
- Chat général : 0.7 - 0.9
- Créatif : 1.0 - 1.5

### Top-p (Nucleus Sampling)

**Range** : 0.0 - 1.0

- **0.9** : Considère les tokens représentant 90% de la probabilité cumulée
- **0.95** : Défaut recommandé
- **1.0** : Tous les tokens considérés

**Recommandations** :
- Précision : 0.8 - 0.9
- Équilibré : 0.95
- Diversité : 0.95 - 1.0

### Max Tokens

**Range** : 1 - 32768

- **1024** : Réponses courtes (~750 mots)
- **2048** : Réponses moyennes (~1500 mots)
- **4096+** : Réponses longues

**Attention** : Limité par le context window du modèle (ex: Mistral 7B = 8192 tokens total).

## Multi-Tier Memory

La génération injecte plusieurs couches de contexte :

### 1. Short-term Memory
Derniers N turns de conversation (2-5 selon taille du modèle).

### 2. Middle-term Memory (Vector)
Top-K messages pertinents via FAISS similarity search (1-2 chunks).

### 3. Long-term Memory (Summary)
Résumé périodique de la conversation (généré tous les 10 messages).

### 4. Knowledge Base Context
Si le modèle a un KB attaché, top-K chunks pertinents (1-3 selon taille).

**Configuration par taille de modèle** :

| Taille | Short | Middle | Long | KB |
|--------|-------|--------|------|-----|
| <2B | 2 turns | 1 | ❌ | 1 |
| 2-4B | 3 turns | ❌ | ❌ | 1 |
| 4-8B | 3 turns | 1 | ✅ | 1 |
| 8-16B | 3 turns | 1 | ✅ | 1 |
| 16B+ | 5 turns | 2 | ✅ | 3 |

Voir `backend/src/utils/prompt_utils.py::get_prompting_strategy()`.

## Bonnes Pratiques

### Limites de Context Window

Vérifier que `short_term + middle_term + long_term + KB + prompt + max_tokens < context_window`.

Exemple Mistral 7B (8192 tokens) :
- System prompt : ~500 tokens
- Short-term (3 turns × 200) : ~600 tokens
- Middle-term : ~300 tokens
- KB (1 chunk) : ~384 tokens
- **Total utilisé** : ~1800 tokens
- **Restant pour génération** : 6400 tokens ✅

### Éviter les Boucles Infinies

Si le modèle génère indéfiniment :
1. Réduire `max_tokens`
2. Augmenter `temperature` (sortir du mode déterministe)
3. Vérifier le prompt (éviter les instructions conflictuelles)

### Performance

- **Streaming** : Réduit la latence perçue (~50ms first token)
- **Cleanup** : Les modèles sont déchargés après 5 min d'inactivité
- **Batch** : Éviter de générer plusieurs réponses simultanées (ressources limitées)

### Debugging

Consulter les logs pour voir le prompt final :

```bash
tail -f backend/logs/backend.log | grep "Final prompt"
```

## Exemples d'Utilisation

### Chat Simple

```python
import requests

# Créer conversation
resp = requests.post('http://127.0.0.1:27182/erudi/conversations', json={
    'llm_id': 1,
    'name': 'Quick Chat'
})
conv_id = resp.json()['id']

# Générer réponse
resp = requests.post(f'http://127.0.0.1:27182/erudi/conversations/{conv_id}/generate', 
                     json={'content': 'Hello!'}, stream=True)

for chunk in resp.iter_content(decode_unicode=True):
    print(chunk, end='', flush=True)
```

### Multi-turn avec Paramètres

```python
# Conversation créative
resp = requests.post('http://127.0.0.1:27182/erudi/conversations', json={
    'llm_id': 1,
    'name': 'Story Writing',
    'temperature': 1.2,
    'top_p': 0.95,
    'max_tokens': 2048
})
conv_id = resp.json()['id']

# Tour 1
requests.post(f'http://127.0.0.1:27182/erudi/conversations/{conv_id}/generate',
              json={'content': 'Write a sci-fi story opening'}, stream=True)

# Tour 2 (contexte automatique)
requests.post(f'http://127.0.0.1:27182/erudi/conversations/{conv_id}/generate',
              json={'content': 'Continue the story'}, stream=True)
```

## API Référence

Documentation complète des endpoints :

- [Conversations Reference](../reference/conversations.md)
- [Schemas Reference](../reference/conversations.md#schemas)
- [Services Reference](../reference/conversations.md#services)

## Voir Aussi

- [Guide LLMs](llms.md) — Charger et gérer les modèles
- [Guide Knowledge Base](knowledge_base.md) — Attacher des KB pour RAG
- [Architecture](../architecture.md) — Comprendre le multi-tier memory
