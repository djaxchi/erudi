# 🧹 Gestion de la propreté du projet Erudi

Guide des bonnes pratiques pour maintenir un repository propre et professionnel.

---

## 📋 Principes directeurs

### Ce qui DOIT être versionné (dans Git)

✅ **Code source** : Backend, frontend, scripts
✅ **Documentation source** : `docs/**/*.md`, `mkdocs.yml`
✅ **Configuration** : `.github/`, `requirements/`, `package.json`
✅ **Scripts d'automatisation** : `scripts/`, `tools/`
✅ **Licences et README** : `LICENSE`, `README.md`

### Ce qui NE DOIT PAS être versionné (dans .gitignore)

❌ **Artifacts buildés** : `site/`, `dist/`, `build/`
❌ **Rapports générés** : `reports/`, logs JSON/CSV temporaires
❌ **Dépendances** : `node_modules/`, `venv/`, `__pycache__/`
❌ **Fichiers système** : `.DS_Store`, `Thumbs.db`
❌ **Secrets** : `.env`, tokens, API keys
❌ **Cache** : `.ruff_cache/`, `.pytest_cache/`, `.mypy_cache/`

---

## 🗂️ Structure du projet Erudi

```
erudi/
├── backend/               # Code source backend (VERSIONNÉ)
│   ├── src/              # Code applicatif
│   ├── tests/            # Tests unitaires/intégration
│   ├── requirements/     # Dépendances Python
│   ├── data/             # PARTIELLEMENT VERSIONNÉ (voir ci-dessous)
│   │   ├── models/       # ❌ Modèles LLM (trop gros, .gitignore)
│   │   ├── indexes/      # ❌ Index FAISS (générés, .gitignore)
│   │   └── migrate/      # ✅ Scripts migration DB (versionnés)
│   └── logs/             # ❌ Logs applicatifs (.gitignore)
│
├── frontend/             # Code source frontend (VERSIONNÉ)
│   ├── src/              # React components
│   ├── public/           # Assets statiques
│   └── dist/             # ❌ Build Electron (.gitignore)
│
├── docs/                 # Documentation MkDocs (VERSIONNÉ)
│   ├── *.md              # Pages narratives
│   ├── reference/        # Pages API générées (VERSIONNÉ car reproductibles)
│   ├── stylesheets/      # CSS custom (VERSIONNÉ)
│   └── map.yaml          # Map docs↔code (VERSIONNÉ car config)
│
├── scripts/              # Scripts d'automatisation (VERSIONNÉ)
│   ├── documentation_audit/  # Scripts audit doc (CI/CD ready)
│   ├── build/            # Scripts de build
│   └── dev/              # Scripts de développement
│
├── reports/              # ❌ Artifacts temporaires (.gitignore)
│   └── doc_audit/        # Rapports JSON/CSV générés par scripts
│
├── site/                 # ❌ Build MkDocs (.gitignore)
├── .gitignore            # ✅ Règles d'exclusion (VERSIONNÉ)
├── mkdocs.yml            # ✅ Config MkDocs (VERSIONNÉ)
└── README.md             # ✅ Documentation projet (VERSIONNÉ)
```

---

## 🎯 Cas particuliers

### Documentation générée (`docs/reference/*.md`)

**Question :** Faut-il versionner les pages API générées ?

**Réponse :** **OUI**, pour plusieurs raisons :

1. **Reproductibilité** : Garantit que le build MkDocs fonctionne même sans re-run des scripts
2. **Traçabilité** : Les diffs Git montrent les changements d'API
3. **CI/CD** : GitHub Pages ou Netlify peuvent build directement sans dépendances lourdes
4. **Onboarding** : Nouveaux contributeurs voient immédiatement la doc complète

**Alternative :** Les générer dynamiquement en CI, mais plus complexe et fragile.

---

### Rapports d'audit (`reports/doc_audit/`)

**Question :** Faut-il versionner les rapports JSON/CSV d'audit ?

**Réponse :** **NON**

1. **Reproductibles** : Scripts `scan_modules.py`, `quality_control.py` peuvent les régénérer à tout moment
2. **Volatilité** : Changent à chaque modification du code
3. **Taille** : Peuvent devenir volumineux (index CSV, logs détaillés)
4. **Pollution Git** : Créent du bruit dans l'historique

**Usage :** Générer en local ou en CI, consulter, puis jeter. Seuls les **scripts** sont versionnés.

---

### Models LLM (`backend/data/models/`)

**Question :** Faut-il versionner les modèles téléchargés ?

**Réponse :** **NON**

1. **Taille** : 1-20 GB par modèle → explosion du repo
2. **Disponibilité** : Téléchargeables depuis HuggingFace
3. **Volatilité** : Changent selon les besoins utilisateur

**Solution :** `.gitignore` + script de download automatique (`backend/src/domains/llms/services.py`)

---

## 🚀 Workflow recommandé

### Avant un commit

```bash
# 1. Vérifier le statut Git
git status

# 2. Vérifier .gitignore respecté
git ls-files --others --ignored --exclude-standard

# 3. Vérifier pas de gros fichiers
git ls-files -z | xargs -0 du -h | sort -h | tail -20

# 4. Lancer les checks qualité
python scripts/documentation_audit/quality_control.py
ruff check backend/src
mypy backend/src
```

---

### Nettoyage périodique

```bash
# Supprimer les artifacts
rm -rf site/ reports/ backend/logs/

# Nettoyer les caches Python
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name '*.pyc' -delete

# Nettoyer les caches Node
rm -rf frontend/node_modules frontend/dist

# Rebuild propre
mkdocs build
cd frontend && npm install && npm run build
```

---

## ✅ Checklist qualité repo

Avant de push vers `origin` :

- [ ] `.gitignore` à jour et respecté
- [ ] Pas de fichiers `>10MB` (sauf assets légitimes)
- [ ] Pas de secrets/tokens exposés
- [ ] `reports/` et `site/` exclus
- [ ] Documentation buildable (`mkdocs build`)
- [ ] Tests passent (`pytest backend/tests`)
- [ ] Linters OK (`ruff`, `mypy`, `eslint`)

---

## 📚 Références

- [Gitignore Best Practices](https://github.com/github/gitignore)
- [Monorepo Structure](https://monorepo.tools/)
- [Python Packaging Guide](https://packaging.python.org/)
- [MkDocs Material](https://squidfunk.github.io/mkdocs-material/)

---

## 🔧 Automatisation CI/CD

### GitHub Actions : Nettoyage automatique

```yaml
name: Cleanup Artifacts

on:
  schedule:
    - cron: '0 2 * * 0'  # Dimanche 2h du matin
  workflow_dispatch:

jobs:
  cleanup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Remove old artifacts
        run: |
          rm -rf reports/
          rm -rf site/
          find . -type d -name __pycache__ -exec rm -rf {} +
          
      - name: Verify .gitignore
        run: |
          # Fail si des fichiers ignorés sont trackés
          if git ls-files --others --ignored --exclude-standard | grep -q .; then
            echo "ERROR: Ignored files are tracked!"
            git ls-files --others --ignored --exclude-standard
            exit 1
          fi
```

---

**Dernière mise à jour :** 25 octobre 2025  
**Responsable :** Équipe Erudi Core
