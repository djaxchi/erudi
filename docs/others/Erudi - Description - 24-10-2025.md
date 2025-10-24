# 🧠 Erudi — Présentation complète

---

## Vision (bigger picture)
Erudi est une application desktop **Ollama-like**, pensée pour **le grand public** autant que pour les ingénieurs.  
Objectif : permettre à n’importe qui de **spécialiser** (personaliser) et **utiliser** des LLMs **localement**, avec une interface simple ("mode facile" aujourd’hui) et la promesse d’un **mode avancé** plus tard. La priorité n’est pas uniquement le fine-tuning brut, mais la **spécialisation globale** : attacher des bases de connaissances, enrichir un modèle avec le jargon/tonalité de l’entreprise, et converser de manière naturelle — le tout **sans cloud**.

**Statut produit :** version **bêta**, sortie très bientôt.

---

## Produit — Ce que fait Erudi aujourd’hui
- Application desktop (UI) pour chatter avec des modèles open-source et les **spécialiser** localement.
- Interface **chat** simple, style conversationnel grand public.
- Gestion de **datasets** & possibilité d'**attacher une knowledge-base** à un modèle : indexation locale dans un vector store (FAISS).  
  - Fichiers supportés pour la KB : **PDF**, **TXT**.
  - Flux : on indexe les fichiers → on vectorise la question de l’utilisateur → on applique **RAG** sur la KB pour enrichir la réponse.
- **Fine-tuning** : en R&D. Prototype très préliminaire sur machines CUDA (version moins que bêta / pas alpha). L’intention est d’avoir un fine-tuning **agnostique au format** des fichiers (drop de CVs, contrats, etc.) — pas besoin d’un dataset JSON structuré Q/A. On vise du **causal fine-tuning** pour transmettre jargon / style, pas (pour l’instant) de l’instruction-tuning. Implementation complète et robuste en cours.
- **Pas** encore de :
  - Agents (pas d’intégration LangChain / LangGraph),
  - Drop de fichiers dans une conversation,
  - Mode vocal,
  - Role-playing model description,
  - Multi-modal (images).
- **Pas** de déploiement serveur / CLI pour l’instant — les modèles sont utilisables via l’UI uniquement. On explore des connexions futures (modes agentiques, extensions web pour mails, interactions terminal, ...).

---

## Communication frontend ↔ backend
- **API REST** exclusivement (pas de WebSocket).

---

## Gestion du contexte conversationnel (détail)
Lors de la construction du prompt/context envoyé au modèle, Erudi concatène (dans cet ordre d’assemblage d’exemples d’usage — mais pas limité) les éléments suivants si présents :

1. **System prompt** (si défini).
2. **Short-term memory** : inclusion verbatim des **n derniers tours** (conversations récentes).
3. **Middle-term memory** : recherche vectorielle dans la mémoire (FAISS) des **n messages** les plus pertinents → insertion verbatim.
4. **Long-term memory** : résumé généré par le LLM de la conversation (summary) → insertion du résumé.
5. **Knowledge base** : si le modèle est attaché à une KB (FAISS), récupération des **n chunks** les plus pertinents via recherche vectorielle → insertion verbatim.
6. **Context prompt** (si l’utilisateur fournit un contexte personnalisé) → ajout verbatim.

Remarques :
- La question de l’utilisateur est vectorisée pour les recherches RAG.
- Le « drop de fichiers dans une conversation » n’est pas encore implémenté.
- Le chat UI permet, pour le moment, paramétrer : **temperature**, **top_p**, **max_tokens**, et **custom system prompt**.

---

## Datasets & Knowledge Base
- **Datasets** : upload local de fichiers (PDF, TXT) pour indexation.
- **Vector Store** : **FAISS** (local).
- **RAG** : question vectorisée → récupération des chunks pertinents → injection en contexte.
- But à terme : accepter n’importe quel fichier sans préparation (fine-tuning agnostique au format).

---

## Fine-tuning — état et ambition
- **État actuel** : R&D. Prototype CUDA existant (très précoce — < bêta, pas alpha). Pas encore satisfaisant pour la release.
- **Ambition** :
  - Fine-tuning **agnostique** au format du dataset fourni par l’utilisateur (pas besoin de structure Q/A).
  - Causal fine-tuning pour apprendre **ton, jargon, tournures**.
  - Ne pas se limiter à instruction-tuning (option envisagée plus tard).
- **Contraintes actuelles** : robustesse, automatisation du pré-traitement, et pipelines sûrs restent à consolider.

---

## Support hardware & runtime (actuel)
- **Mac Silicon (M1+)**
  - Techno : **MLX_LM** pour quantization, inference et (partiellement) entraînement.
  - Fine-tunings complets sur Mac Silicon : **pas encore développés**.
- **Windows / Linux GPUs NVIDIA**
  - Support CUDA : **inférence et fine-tuning** via Transformers.
  - Quantization actuelle : **bitsandbytes**. Benchmarks en cours pour alternatives.
- **Windows / Linux CPUs, Mac Intel, GPUs AMD (ROCm)**
  - Option d’inférence/quantization via **llama.cpp** (ciblé CPU) envisagée.
  - **llama.cpp n’est pas encore implémenté** dans Erudi.
  - Fine-tuning pour ces plateformes : à l’étude, non implémenté aujourd’hui.

---

## Frameworks & environnement dev / build
- **Langage** : Python — **dev supporté en 3.9+**.  
- **Build / releases** : actuellement **Python 3.12** pour le packaging des releases.
- **Backend** :
  - **FastAPI**
  - **uvicorn** (pour lancer l’API)
  - **pyinstaller** (pour packager l’app backend/éléments natifs)
- **Frontend** : **Electron** (desktop) + **React** + **Tailwind** pour l’UI.
- **ML & infra** :
  - **HuggingFace Transformers** (pour CUDA workflows)
  - **bitsandbytes** (quantization sur NVIDIA — en usage)
  - **MLX_LM** (Mac Silicon)
  - **FAISS** (vector store local)

---

## Positionnement produit
- **But** : fournir un outil **Ollama-like** mais **accessible au grand public** (interface chat simple) tout en restant puissant pour les ingénieurs.  
- **Modes** : **mode facile** (disponible dès la bêta) → **mode complexe** à venir.  
- **Concentration** : la priorité est la **spécialisation** (make models useful for real people/corporates locally), pas seulement le fine-tuning brut.

---

## Business model et commercialisation (état)
- **Phase actuelle** : très early-stage, **pre-revenue**.
- **B2C** : version **gratuite** pour la bêta / première version.  
  - Possibilité future : gratuit jusqu’à **3 modèles spécialisés**, puis tarification au-delà.
- **B2B** : principal levier monétisation envisagé — licences/packaging pour entreprises qui veulent **déployer Erudi sur le parc de machines local** (machines/PCs fournis aux collaborateurs), **pas** sur serveurs ou cloud. Verticale cible encore à définir. Pricing et offres en cours de réflexion.
- **Distribution** : téléchargement via le site officiel — **www.erudi.app/** (installeur adapté selon hardware). **Pas** de CLI prévue.
- **Canaux marketing initiaux** : **LinkedIn** uniquement (pour l’instant).

---

## Cibles (release beta)
- **Public large** : l’UI chat-like permet à tout le monde d’essayer Erudi.
- L’équipe décidera des verticales B2B plus tard. Aujourd’hui : **ciblage large** pour la bêta.

---

## Limites et éléments non implémentés (à savoir)
- Agents autonomes / intégration LangChain / LangGraph : **non implémentés**.
- Drop de fichiers en conversation, vocal, role-playing description, multimodal images : **non implémentés**.
- Déploiement de modèles via Erudi (serveur/CLI) : **non disponible** — modèles utilisables uniquement via l’UI.
- llama.cpp : non implémenté aujourd’hui.

---

## Stack résumé
- **Frontend Desktop** : Electron + React + Tailwind
- **Backend** : Python (3.9+ dev, 3.12 build), FastAPI, uvicorn, pyinstaller
- **ML** : Transformers (CUDA), bitsandbytes, MLX_LM (Mac Silicon), FAISS
- **Storage** : stockage local / index FAISS
- **Distribution** : instal via www.erudi.app (installers)

---

## L'équipe
- Djalil Chikhi
- Rayan Hanader
- Youssef Laatar
- Youssef Chaouki
- Sami Taider
- Mathieu Jarry

## A retenir (clé, direct)
- Erudi = **outil desktop** pour **spécialiser** et **utiliser** LLMs **localement**, accessible au grand public et aux ingénieurs.
- **Bêta imminente**. Interface chat simple, mode facile aujourd’hui.
- **RAG + KB (FAISS)** intégrés : PDF/TXT indexés localement, question vectorisée → RAG.
- **Fine-tuning** : R&D précoce (prototype CUDA très primaire). Objectif : fine-tuning **agnostique au format** pour apprendre jargon/ton sans dépendre d’un dataset structuré.
- **Support hardware** : Mac Silicon (MLX_LM), NVIDIA GPUs (CUDA + bitsandbytes), options CPU/AMD à l’étude.
- **Communication** : API REST. **Pas** de WebSocket.
- **Distribution & Business** : bêta gratuite via www.erudi.app ; B2B future pour machines locales ; early-stage, pre-revenue.
- **Non implémenté** : agents, drop fichiers dans conv, vocal, multi-modal, packaging serveur.