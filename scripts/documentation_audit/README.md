# � Documentation Audit & Generation Tools

Scripts pour l'audit, la génération et la maintenance de la documentation Erudi.  
**Réutilisables pour CI/CD et re-checks futurs.**

---

## 🎯 Workflow complet

### 1️⃣ Scan initial du code source

```bash
cd /path/to/erudi

# Scanner tous les modules Python
python scripts/documentation_audit/scan_modules.py \
  --src backend/src \
  --out reports/doc_audit
```

**Génère :**
- `reports/doc_audit/module_index.csv` - Index de tous les objets
- `reports/doc_audit/missing_docstrings.json` - Docstrings manquantes

---

### 2️⃣ Audit qualité

```bash
# Analyser la couverture et conformité
python scripts/documentation_audit/quality_control.py
```

**Génère :**
- `reports/doc_audit/quality_report.json` - Métriques de qualité
- Stats par catégorie (modules, classes, fonctions, méthodes)
- Top 10 modules à documenter en priorité

---

### 3️⃣ Génération de la map

```bash
# Créer la map docs↔code
python scripts/documentation_audit/generate_map.py
```

**Génère :**
- `docs/map.yaml` - Carte de la structure backend organisée par domaines

---

### 4️⃣ Génération des pages API

```bash
# Générer les pages de référence MkDocs
python scripts/documentation_audit/generate_reference_pages.py \
  --map docs/map.yaml \
  --out docs/reference
```

**Génère :**
- `docs/reference/*.md` - Pages API avec directives mkdocstrings

---

### 5️⃣ Build de la documentation

```bash
# Build final
mkdocs build

# Ou en mode dev avec live reload
mkdocs serve --dev-addr 127.0.0.1:8001
```

---

## 📦 Scripts détaillés

### `scan_modules.py`

Scanne récursivement tous les modules Python du backend.

**Usage :**

```bash
python scripts/documentation_audit/scan_modules.py \
  --src backend/src \
  --out reports/doc_audit
```

**Génère :**

- `module_index.csv` - Index complet (module, classe, fonction, méthode)
- `missing_docstrings.json` - Rapport des docstrings manquantes

---

### `quality_control.py`

Analyse qualité : couverture, conformité PEP 257, top modules à documenter.

**Usage :**

```bash
python scripts/documentation_audit/quality_control.py
```

**Output :** Rapport console + JSON optionnel

---

### `generate_map.py`

Crée `docs/map.yaml` depuis `module_index.csv`, organisé par domaines fonctionnels.

**Usage :**

```bash
python scripts/documentation_audit/generate_map.py
```

**Output :** `docs/map.yaml`

---

### `generate_reference_pages.py`

Génère les pages `.md` pour MkDocs avec directives `::: module.path`.

**Usage :**

```bash
python scripts/documentation_audit/generate_reference_pages.py \
  --map docs/map.yaml \
  --out docs/reference
```

**Output :** `docs/reference/{domain}.md`

---

## 🔄 Workflow recommandé

### Avant un commit majeur

```bash
# 1. Scan complet
python scripts/documentation_audit/scan_modules.py --src backend/src --out reports/doc_audit

# 2. Vérification qualité
python scripts/documentation_audit/quality_control.py

# 3. Régénération map si structure a changé
python scripts/documentation_audit/generate_map.py

# 4. Régénération pages API
python scripts/documentation_audit/generate_reference_pages.py --map docs/map.yaml --out docs/reference

# 5. Build doc
mkdocs build
```

---

## 🚀 Integration CI/CD

Ces scripts peuvent bloquer les PRs avec couverture insuffisante :

**Critères gate qualité :**

- Docstrings manquantes sur fonctions/classes publiques
- Non-conformité PEP 257
- Régression de couverture documentation (<90%)

**Exemple `.github/workflows/doc-quality.yml` :**

```yaml
name: Documentation Quality

on: [pull_request]

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install pyyaml
      
      - name: Run doc audit
        run: |
          python scripts/documentation_audit/scan_modules.py --src backend/src --out reports/doc_audit
          python scripts/documentation_audit/quality_control.py
      
      - name: Check coverage threshold
        run: |
          python -c "
          import json
          with open('reports/doc_audit/missing_docstrings.json') as f:
              data = json.load(f)
          coverage = 100 - (data['summary']['total_missing'] / data['summary']['total_objects'] * 100)
          print(f'Coverage: {coverage:.2f}%')
          exit(0 if coverage >= 90 else 1)
          "
```

---

## 📂 Artifacts

**Versionnés (dans le repo) :**

- ✅ Scripts Python (`scripts/documentation_audit/*.py`)
- ✅ Documentation générée (`docs/**/*.md`)
- ✅ Map (`docs/map.yaml`)

**Non versionnés (`.gitignore`) :**

- ❌ Rapports JSON/CSV (`reports/doc_audit/`)
- ❌ Site MkDocs buildé (`site/`)

**Rationale :**

- Scripts = code source → versionnés
- Rapports = artifacts générés → non versionnés (reproductibles via scripts)

---

## 🛠️ Maintenance

Ces scripts sont **maintenus en parallèle du backend** :

- Modification de structure backend → adapter filtres dans scripts
- Ajout de nouveaux domaines → mettre à jour catégorisation
- Évolution critères qualité → ajuster `quality_control.py`

**Compatibilité :** Python 3.9+, pas de dépendances lourdes (seulement `pyyaml`)

---

## 📌 Scripts legacy (optionnels)

### `generate_phase2_report.py`

Rapport spécifique Phase 2. **Jetable après Phase 2 terminée.**

### `scan_docstrings.py`

Version standalone de scan. **Redondant avec `scan_modules.py`**, conservé pour compatibilité.

---

## ✅ Checklist qualité

Avant de commit :

- [ ] `scan_modules.py` exécuté sans erreurs
- [ ] `quality_control.py` affiche couverture ≥90%
- [ ] `generate_reference_pages.py` génère toutes les pages
- [ ] `mkdocs build` réussit sans erreurs
- [ ] Documentation visible sur `mkdocs serve`
