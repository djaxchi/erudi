# Scripts d'Aide pour Erudi

Ce dossier contient des scripts pour automatiser le développement et le build d'Erudi.

## 📜 Scripts Disponibles

### 1. `dev-start.sh` - Démarrage du mode développement
```bash
./build-scripts/dev-start.sh
```
**Utilisation :** Démarre automatiquement le backend Python et le frontend Electron en mode développement.

**Ce que fait le script :**
- Vérifie les dépendances (venv Python, node_modules)
- Installe automatiquement ce qui manque
- Démarre le backend FastAPI en arrière-plan
- Vérifie que le backend répond avant de démarrer le frontend
- Lance l'application Electron
- Nettoie automatiquement à la fermeture (Ctrl+C)

---

### 2. `build-erudi.sh` - Build complet de l'application
```bash
./build-scripts/build-erudi.sh
```
**Utilisation :** Créé un build complet prêt à distribuer avec un nouveau backend.

**Ce que fait le script :**
- Build le backend Python avec PyInstaller
- Copie le backend vers le dossier frontend
- Vérifie les dépendances frontend
- Build l'application Electron avec electron-forge
- Créé le DMG installer macOS
- Propose d'ouvrir le DMG à la fin

**Durée :** ~2-5 minutes selon la machine

---

### 3. `quick-backend-rebuild.sh` - Rebuild rapide du backend uniquement
```bash
./build-scripts/quick-backend-rebuild.sh
```
**Utilisation :** Quand vous avez modifié SEULEMENT le code backend Python.

**Ce que fait le script :**
- Rebuild uniquement le backend avec PyInstaller
- Copie la nouvelle version vers frontend/
- Plus rapide que le build complet

**Durée :** ~30 secondes

**Note :** Après ce script, vous devez encore faire `npm run make` dans frontend/

---

### 4. `test-build.sh` - Vérification du build
```bash
./build-scripts/test-build.sh
```
**Utilisation :** Vérifier que tout est correctement configuré.

**Ce que fait le script :**
- Vérifie que l'exécutable backend existe
- Contrôle la configuration Electron Forge
- Teste la syntaxe des fichiers JS
- Vérifie la présence du DMG
- Donne un rapport complet

---

## 🔄 Workflows Typiques

### Développement quotidien
```bash
# Démarrer le dev
./build-scripts/dev-start.sh

# Arrêter avec Ctrl+C quand terminé
```

### Après modification du backend Python
```bash
# Option 1: Rebuild rapide (puis npm run make dans frontend/)
./build-scripts/quick-backend-rebuild.sh
cd frontend && npm run make

# Option 2: Build complet (plus lent mais plus sûr)
./build-scripts/build-erudi.sh
```

### Après modification du frontend seulement
```bash
cd frontend
npm run make
```

### Build pour release/distribution
```bash
# Build complet
./build-scripts/build-erudi.sh

# Vérifier le build
./build-scripts/test-build.sh

# Le DMG est dans frontend/out/make/Erudi-Installer.dmg
```

---

## 🐛 Dépannage

### Erreur "Permission denied"
```bash
chmod +x build-scripts/*.sh
```

### Backend ne démarre pas en dev
```bash
# Vérifier les logs
tail -f /tmp/erudi-backend.log

# Ou redémarrer proprement
pkill -f uvicorn
./build-scripts/dev-start.sh
```

### Build PyInstaller échoue
```bash
cd backend
source venv/bin/activate
pip install --upgrade pyinstaller
pyinstaller --clean backend.spec
```

### DMG trop volumineux
Le DMG peut faire 300MB+ à cause des dépendances Python (PyTorch, etc.).
C'est normal pour une app avec des modèles ML embarqués.

---

## 🎯 Conseils d'Utilisation

1. **Toujours utiliser `dev-start.sh` pour le développement** - il gère automatiquement le backend et frontend

2. **Tester avec `test-build.sh` avant de distribuer** - évite les mauvaises surprises

3. **Utiliser `quick-backend-rebuild.sh` pour les petites modifications backend** - beaucoup plus rapide

4. **Le DMG est prêt à distribuer** - il contient tout ce qu'il faut, backend inclus

5. **Logs disponibles dans `/tmp/erudi-backend.log`** pour débugger les problèmes backend

6. **Premier lancement sur macOS** - peut demander l'autorisation de sécurité pour le backend non-signé