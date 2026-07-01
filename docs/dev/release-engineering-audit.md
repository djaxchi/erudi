# Release Engineering — Audit & Roadmap (build/release multi-OS)

Audit du 2026-06-16, branche `main`. Confronte l'état réel du repo au référentiel
« best practices open-source » (apps Mac + Windows + Linux, builds de prod,
auto-release, gating par tests, supply-chain). Établi par 4 audits parallèles
croisant lecture de code + `gh`/`git` live. Évidence en `fichier:ligne`.

> **STATUS 2026-07-01 — largement livré.** Le gros de cette roadmap est fait :
> pipeline release multi-OS signé (mac notarisé) + auto-update sur tag `vX.Y.Z`
> (`release.yml`, 5 legs) — #110 fermée ; gate de merge full-app boot-to-`ready`
> (`app-build-smoke.yml`) — #92 ; promote atomique all-green (`release-promote.yml`)
> — #115 ; snapshots catalogue build-time + régénération CI — #112/#114. Première
> release réelle **`v2.0.0` buildée 5/5** (draft en QA, #139). Restent ouverts :
> Windows signing (SignPath, futur), Intel mac, merge queue (#94). Ce doc reste la
> référence historique de l'audit et des décisions de périmètre.

> **Décisions de périmètre (user, 2026-06-16)** : macOS = pipeline signé+notarisé
> complet (compte Apple dispo), **Intel conservé** ; Windows = non signé pour
> l'instant, voie future = **SignPath Foundation** (mainteneur hors US/Canada →
> Azure Trusted Signing N/A) ; cibles = macOS arm64 + Intel, Windows x64, Linux
> deb/rpm.

---

## 0. Deux constats transverses à trancher AVANT tout

1. **Le repo est `private` avec une LICENCE propriétaire « All rights reserved »**
   (`LICENSE`), alors que l'objectif affiché est « best practices open-source ».
   Conséquence concrète : sur un repo **public**, secret-scanning, push-protection,
   code-scanning (CodeQL), Dependabot et OpenSSF Scorecard sont **gratuits** ; sur
   un repo **privé** ils exigent **GitHub Advanced Security (payant)**. La décision
   « passe-t-on réellement en open-source public ? » conditionne donc tout le volet
   sécurité/supply-chain (gratuit vs payant, ou repli sur des équivalents CI
   `gitleaks`/`pip-audit`).

2. **Le pipeline n'est PAS greenfield** : 4 releases publiées (v1.0.2/3/4 + draft
   v1.0.0) avec manifestes electron-updater. On **durcit et complète** un existant
   partiellement fonctionnel — on ne part pas de zéro.

---

## 1. Ce qui EXISTE et FONCTIONNE (2 cibles prouvées)

| Élément | Évidence |
|---|---|
| **CI PR-gate backend** : Ubuntu, setup-python 3.12 + cache pip, `compileall` + `ruff` + import + `pytest --ignore=tests/e2e -m "not mlx_only"` | `backend-ci.yml:15-51` |
| **CI PR-gate frontend** : Node 20 + cache npm, `lint:check` + `format:check` | `frontend-ci.yml:15-37` |
| **CD tag-triggered** (`on: push tags v*`) publiant sur GitHub Releases | `release.yml:5-10` |
| **Build Windows-CUDA-12.1** : PyInstaller `backend.spec` → forge package → electron-builder NSIS `--publish always` | `release.yml:16-75`, `backend.spec` |
| **Build macOS-arm64** signé+notarisé : `backend-mac-silicon.spec` (collect_all mlx/mlx_vlm) → codesign manuel de chaque Mach-O avec `assets/entitlements.mac.plist` → notarytool → stapler → publish | `release.yml:77-253`, `backend-mac-silicon.spec:55-59,253` |
| **Handoff backend→app (CI)** : PyInstaller `--distpath backend/dist`, consommé par forge `extraResource: ["../backend/dist/backend"]`, résolu au runtime | `release.yml:47,104`, `forge.config.js:14`, `main.js:86-88` |
| **Contrat JSON run.py préservé** dans le gelé (`console=True`, events parsés) | `backend.spec:306`, `main.js:203-215` |
| **Résolution de chemins frozen vs dev** (postgres/data/models, mac/win/linux) | `run.py:101-126`, `runtime_paths.py:133-151`, `postgres_runtime.py:76-86` |
| **electron-updater câblé côté code** : import packaged-only, `checkForUpdates` au lancement + toutes les 4 h, `update-downloaded → quitAndInstall` | `main.js:12-23,825-829,860-894` |
| **Commits GPG-signés** (clé `B5690EEEBB952194`) | `git log --show-signature` |

---

## 2. Ce qui EXISTE mais est CASSÉ / FRAGILE

| Problème | Gravité | Évidence |
|---|---|---|
| **Dualité electron-forge + electron-builder, inversée.** forge est le packageur actif (mac local = `npm run make`), builder n'est qu'un wrapper `--prepackaged`. Deux définitions d'app qui dérivent (`productName` = `erudi` vs `Erudi`). | Élevée | `package.json:8-15`, `forge.config.js:1-182`, `electron-builder.yml:5-6`, `build-mac-silicon.sh:114-116` |
| **Deux fichiers d'entitlements divergents.** Celui que forge utilise (`entitlements.plist`) a `disable-library-validation=false` + `allow-dyld-environment-variables=false` → **casserait le backend PyInstaller+MLX au lancement** si jamais `APPLE_SIGNING_IDENTITY` est exporté. Le bon (`assets/entitlements.mac.plist`) n'a pas `network.server`. | Élevée (footgun latent) | `entitlements.plist:10-13`, `assets/entitlements.mac.plist:4-15`, `forge.config.js:46` |
| **Backend non signé explicitement** : pas de `mac.binaries` dans electron-builder.yml ; l'EXE PyInstaller est `codesign_identity=None`. Le CI re-signe à la main (OK aujourd'hui) mais rien ne nomme le binaire pour la voie builder. | Élevée | `electron-builder.yml` (pas de `mac.binaries`), `backend-mac-silicon.spec:254-255`, `release.yml:155-198` |
| **Ordre notarisation suspect** : build DMG `--publish never` → `stapler staple` → **re-run** `electron-builder --publish always` qui **reconstruit** le DMG → l'artefact publié pourrait être **non stapled**. À vérifier en live. | Élevée | `release.yml:205-208,242,250-253` |
| **Windows = CUDA-only.** La release installe `win-cuda-121-prod.txt` + `backend.spec` (CUDA) ; aucun `llama-server` CPU n'est bundlé → sur une machine Windows **sans NVIDIA**, le fallback CPU n'a pas de binaire à lancer. (À confirmer au runtime.) | Élevée (produit) | `release.yml:43,47`, `backend.spec:53-65` (cuda/bin only, `if IS_WIN`) |
| **`backend-cpu.spec` ne build pas.** Il `exec_module` `backend.spec` comme sous-module → namespace de spec vide (PyInstaller ne trouve aucun graphe) ; et sa prémisse `ERUDI_BUILD_VARIANT` est fausse (`backend.spec` ne lit jamais cette var). `except: pass` masque l'échec. Jamais invoqué. | Moyenne | `backend-cpu.spec:13,21-37` |
| **Copie `frontend/backend/` orpheline** dans les scripts manuels : forge lit `../backend/dist/backend`, pas `./backend` → le `cp` est mort. | Faible | `build-mac-silicon.sh:88-93`, `build-win-cuda-121.ps1:122-127` |
| **`releaseType: release`** (pas `draft`) → publication publique immédiate, sans étape de vérif. | Moyenne | `electron-builder.yml:17` |
| **BUILD.md / NOTARIZATION.md périmés** : pointent `build-scripts/`, `run_mac.py`, SQLite, port 8000 — tout obsolète. Trompent quiconque build. | Moyenne | `BUILD.md`, `NOTARIZATION.md` |

---

## 3. Ce qui est ASPIRATIONNEL (annoncé mais ne se construit pas)

Sur 5 cibles, **seules 2 ont une chaîne spec→requirements→handoff→signing prouvée**
(win-CUDA, mac-arm64). Les 3 autres sont des coquilles :

| Cible | État | Évidence |
|---|---|---|
| **macOS Intel / mac-CPU** | MANQUANT. Pas de spec Intel ; `meta/mac-intel-specs.txt` **vide** → install prod sans aucun moteur LLM. Tout est arm64-only (`--arch arm64` codé en dur). | `meta/mac-intel-specs.txt`, `package.json:12,14`, `backend-mac-silicon.spec:253` |
| **Linux deb/rpm** | MANQUANT. Pas de spec Linux, pas de script, pas de job release. `meta/linux-specs.txt` **vide**. Makers deb/rpm déclarés dans forge mais sans backend derrière. | `forge.config.js:128-143`, `meta/linux-specs.txt` |
| **Windows-CPU** | CASSÉ. Seul `backend-cpu.spec` le vise, et il ne build pas (§2). | `backend-cpu.spec` |
| **Bundling llama-server CPU** (cause racine des 3) | Les binaires CPU sont **commités** (`artifacts/llama-cpp/cpu/bin/llama-server`) mais **aucun spec ne les bundle** (seul `cuda/bin` sur Windows). | `backend.spec:53-65` |

---

## 4. Ce qui MANQUE entièrement

**Gating CI→CD**
- `release.yml` n'a **aucun `needs:`** sur la CI → **un build rouge peut publier une release signée**. (`release.yml` — grep `needs:` = 0)
- **Aucune branch-protection / ruleset** sur `main` (`gh api .../branches/main/protection` → 404 ; `.../rulesets` → `[]`) → **la CI est purement consultative**, un merge rouge sur `main` est possible. Filtres de chemin (`backend/**`/`frontend/**`) → un PR ne touchant que la config racine merge **sans aucune CI**.
- Pas d'`environment:` protégé sur le job release (qui détient les secrets Apple/CSC).

**Matrice de build**
- Aucune `strategy.matrix` / `fail-fast: false` ; 2 jobs hand-codés, 2 cibles seulement.
- Pas d'`upload-artifact` (tout va direct en Release ; un publish raté perd tout).
- Pas de cache electron ; pas de cache pip dans `release.yml`.

**Tests**
- **Frontend : zéro test** (pas de script `test`, ni vitest/jest/playwright). Renderer, `preload.js`, IPC, spawn backend dans `main.js` non testés.
- **Backend e2e : vide** (`tests/e2e/` = `.gitkeep` seul ; exclu de la CI de toute façon).
- **Aucun test d'artefact packagé** : `test_spec_files.py` valide les fichiers `.spec`, pas un binaire construit. Aucun smoke-test « l'app se lance + le backend boote » avant publication.

**Supply-chain / sécurité (recoupe #89)**
- **`.env` et `backend/.env` toujours suivis** (`git ls-files`) — même classe Critical que #89, non corrigé.
- Suite sécurité GitHub **OFF** (`security_and_analysis: null`) : Dependabot, secret-scanning, code-scanning tous désactivés (c'est pourquoi le token HF de #89 n'a jamais été détecté).
- **Aucune action SHA-pinnée** (tout en `@v4`/`@v5` flottant).
- `permissions:` absent des 2 workflows CI (pas de moindre-privilège) ; `release.yml` a `contents: write` (OK) mais pas d'OIDC.
- Pas de provenance/attestation (`actions/attest*`), pas de SBOM.
- **Tags non signés** (lightweight, pas annotés/GPG).
- Pas de `SECURITY.md`, `CODEOWNERS`, `.github/dependabot.yml`, templates issue/PR (ceux présents sont les vendored llama-cpp).

**Versioning / release**
- Pas d'automatisation de version/changelog (release-please/changesets/semantic-release absents). Versions bumpées à la main.

---

## 5. À TESTER (ne peut pas être tranché statiquement — vérif live requise)

1. **DMG publié réellement stapled ?** Télécharger l'asset de `v1.0.4`, `xcrun stapler validate` + `spctl -a -vvv -t install`. (Bug d'ordre §2.)
2. **Windows sans NVIDIA** : l'installeur CUDA publié lance-t-il l'inférence CPU, ou crashe-t-il faute de `llama-server` CPU bundlé ?
3. **`backend-cpu.spec` / `mac-intel-prod.txt`** : tentent-ils seulement de builder ? (Jamais exercés en CI.)
4. **Update N-1 → N réel** sur mac et Windows (le handshake forge-build vs builder-manifest tient-il ?).
5. **Required status checks côté serveur** : confirmer dans Settings si `backend-ci`/`frontend-ci` sont requis-pour-merge (sinon CI consultative).

---

## 6. Roadmap proposée (phasée, priorisée)

### Phase 0 — Décisions bloquantes (toi)
- Repo **public open-source** (licence OSI + sécurité gratuite) **ou** privé (GHAS payant / repli CI) ?
- Confirmer périmètre cibles (Intel mac coûte un 2ᵉ build CPU complet ; Linux idem).

### Phase 1 — Sécurité & gouvernance (rapide, fort ROI, recoupe #89)
- `git rm --cached .env backend/.env` + purge historique + rotation des secrets.
- Branch-protection/ruleset sur `main` : PR + 1 review (≠ auteur), checks requis (`backend-ci`+`frontend-ci`), historique linéaire, no force-push, commits signés (déjà GPG, juste à imposer).
- SHA-pin toutes les actions ; `permissions: contents: read` sur les 2 CI ; `concurrency`.
- `.github/dependabot.yml` (npm + pip + github-actions) ; `SECURITY.md` ; `CODEOWNERS` ; templates.
- Activer (si public) secret-scanning + push-protection + CodeQL ; sinon `gitleaks`+`pip-audit`+`npm audit` en CI.

### Phase 2 — Consolider le packageur (lever la dualité)
- Standardiser sur **electron-builder**, sortir forge du chemin de release.
- **Un seul** fichier d'entitlements corrigé (`disable-library-validation`, `allow-dyld-environment-variables`, `allow-unsigned-executable-memory`, `network.server/.client`) ; supprimer `entitlements.plist`.
- `extraResources` backend + `mac.binaries` (signer le binaire gelé explicitement).
- `releaseType: draft` ; refaire les fuses Electron sous builder.
- Réécrire BUILD.md/NOTARIZATION.md.

### Phase 3 — Gating CI→CD + build-smoke
- Workflow réutilisable (lint+test+**build-smoke** = `electron-builder package` no-publish + boot du backend gelé attendant `{"event":"ready"}`) que `release.yml` `needs:`.
- `environment: release` protégé (reviewer requis) avant publish.
- Matrice `fail-fast: false`.

### Phase 4 — Compléter les cibles
- Spec mac-Intel (CPU) + leg `macos-15-intel`, **ou** décision explicite d'abandonner Intel.
- Spec Linux + script + leg `ubuntu-latest` (makers deb/rpm déjà là).
- Réparer `backend-cpu.spec` (self-contained) + **bundler `artifacts/llama-cpp/cpu/bin`** dans tous les targets CPU ; ajouter un leg Windows-CPU.
- Build mac dual-arch en **une** invocation builder (évite l'écrasement `latest-mac.yml`).
- Pin PyInstaller (`meta/build.txt`) ; `requires-python = ">=3.12,<3.13"`.

### Phase 5 — Auto-release & tests
- **release-please** (PR de version + CHANGELOG depuis `type(scope):`) → tag → CD.
- Tests frontend (Vitest + Playwright sur build packagé) ; peupler `tests/e2e/`.
- Provenance `actions/attest-build-provenance` + SBOM + tags annotés GPG ; `stagingPercentage` ; procédure de yank documentée.

---

## 7. Ancres fichier:ligne clés
- CI/CD : `release.yml` (pas de `needs:`/matrice, ordre staple `:205-253`, codesign manuel `:155-198`), `backend-ci.yml:51`, `frontend-ci.yml:31-37`.
- Packaging : `forge.config.js:14,46,128-143`, `electron-builder.yml:13-17,40-53`, `package.json:8-15`, `main.js:86-88,825-894`.
- Entitlements : `entitlements.plist:10-13` (mauvais), `assets/entitlements.mac.plist` (bon, sans `network.server`).
- Specs : `backend.spec:53-65`, `backend-mac-silicon.spec:55-59,253`, `backend-cpu.spec:13,21-37`.
- Requirements : `meta/mac-intel-specs.txt` (vide), `meta/linux-specs.txt` (vide), `entrypoints/prod/*`.
- Gouvernance : `.env`/`backend/.env` suivis, `LICENSE` (propriétaire), pas de `SECURITY.md`/`CODEOWNERS`/`dependabot.yml`.
