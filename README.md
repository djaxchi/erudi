# Erudi - Application Electron avec Backend Python

Une application de bureau basée sur Electron avec un backend FastAPI intégré, permettant de gérer des modèles de langage locaux et des conversations IA.

## 📋 Prérequis

- **Node.js** >= 18
- **npm** >= 8
- **Python** >= 3.11
- **Docker** (optionnel pour le développement)
- **PyInstaller** pour la création de l'exécutable backend

## � Installation pour le Développement

### 1. Cloner le projet
```bash
git clone https://github.com/djaxchi/erudi.git
cd erudi
```

### 2. Configuration du Backend Python

#### Option A: Avec environnement virtuel (recommandé)
```bash
cd backend
python -m venv venv

# Sur macOS/Linux:
source venv/bin/activate
# Sur Windows:
# .\venv\Scripts\activate

pip install -r requirements.txt
```

#### Option B: Avec Docker
```bash
cd backend
docker build -t erudi-backend .
docker run -v ${PWD}/data:/app/data -p 8000:8000 erudi-backend
```

### 3. Installation des dépendances Frontend
```bash
cd frontend
npm install
```

### 4. Lancement en mode développement
```bash
# Terminal 1 - Backend (si Option A)
cd backend
source venv/bin/activate  # ou .\venv\Scripts\activate sur Windows
uvicorn app.main:app --reload --port 8000

# Terminal 2 - Frontend
cd frontend
npm start
```

## 📦 Build de Production macOS - Tutoriel Step-by-Step

### Étape 1: Préparer le Backend Python

1. **Activer l'environnement virtuel backend**
   ```bash
   cd backend
   source venv/bin/activate
   ```

2. **Installer PyInstaller si pas déjà fait**
   ```bash
   pip install pyinstaller
   ```

3. **Construire l'exécutable backend avec PyInstaller**
   ```bash
   # Depuis le dossier backend/
   pyinstaller backend.spec
   ```

   Cela va créer:
   - `dist/backend/` - Le dossier de distribution
   - `dist/backend/backend` - L'exécutable principal
   - `dist/backend/_internal/` - Les dépendances Python

### Étape 2: Copier le Backend vers le Frontend

1. **Nettoyer l'ancien backend s'il existe**
   ```bash
   cd ../frontend
   rm -rf backend/
   ```

2. **Copier le nouveau build du backend**
   ```bash
   # Copier tout le dossier de distribution PyInstaller
   cp -r ../backend/dist/backend ./backend
   ```

3. **Vérifier la structure**
   ```bash
   ls -la backend/
   # Doit contenir:
   # backend (exécutable)
   # _internal/ (dossier des dépendances)
   ```

### Étape 3: Configuration du Build Electron

1. **Vérifier le fichier forge.config.js**
   ```javascript
   // frontend/forge.config.js
   module.exports = {
     makers: [
       {
         name: '@electron-forge/maker-dmg',
         config: {
           format: 'ULFO'
         }
       },
       {
         name: '@electron-forge/maker-zip',
         platforms: ['darwin']
       }
     ],
     plugins: [
       {
         name: '@electron-forge/plugin-webpack',
         config: {
           mainConfig: './webpack.main.config.js',
           renderer: {
             config: './webpack.renderer.config.js',
             entryPoints: [{
               html: './public/index.html',
               js: './src/renderer.js',
               name: 'main_window',
               preload: {
                 js: './src/preload.js'
               }
             }]
           }
         }
       }
     ],
     packagerConfig: {
       asar: {
         unpack: "backend/**/*"
       },
       extraResource: [
         "./backend"
       ]
     }
   };
   ```

2. **Vérifier la configuration dans main.js**
   ```javascript
   // Le code pour résoudre le chemin du backend packagé
   function resolvePackagedBackendPath() {
     const candidates = [
       path.join(process.resourcesPath, 'backend', 'backend', 'backend'),
       path.join(process.resourcesPath, 'backend', 'backend'),
       path.join(process.resourcesPath, 'app.asar.unpacked', 'backend', 'backend'),
     ];
     
     for (const c of candidates) {
       if (fs.existsSync(c) && fs.statSync(c).isFile()) {
         return c;
       }
     }
     return null;
   }
   ```

### Étape 4: Build de l'Application

1. **Nettoyer les builds précédents**
   ```bash
   rm -rf out/
   ```

2. **Construire l'application**
   ```bash
   npm run make
   ```

   Cela va créer:
   - `out/make/Erudi-Installer.dmg` - L'installateur DMG
   - `out/make/zip/darwin/arm64/erudi-darwin-arm64-*.zip` - Archive ZIP

### Étape 5: Test et Distribution

1. **Monter le DMG pour tester**
   ```bash
   open out/make/Erudi-Installer.dmg
   ```

2. **Installer l'application**
   - Glisser `erudi.app` vers le dossier Applications
   - La première fois, macOS peut bloquer l'exécution (Gatekeeper)

3. **Résoudre les problèmes de sécurité macOS**
   ```bash
   # Si l'app est bloquée par Gatekeeper:
   # Aller dans Préférences Système > Confidentialité et sécurité
   # Cliquer sur "Ouvrir quand même" pour erudi.app
   
   # Ou utiliser la ligne de commande:
   sudo xattr -rd com.apple.quarantine /Applications/erudi.app
   ```

## 🔧 Scripts Utiles

### Build Rapide (après changements backend)
```bash
#!/bin/bash
# build-erudi.sh

echo "🔄 Building backend with PyInstaller..."
cd backend
source venv/bin/activate
pyinstaller backend.spec

echo "📦 Copying backend to frontend..."
cd ../frontend
rm -rf backend/
cp -r ../backend/dist/backend ./backend

echo "⚡ Building Electron app..."
npm run make

echo "✅ Build completed! DMG available at:"
echo "   $(pwd)/out/make/Erudi-Installer.dmg"
```

### Script de Développement
```bash
#!/bin/bash
# dev-start.sh

# Démarrer le backend en arrière-plan
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

# Démarrer le frontend
cd ../frontend
npm start

# Nettoyer à la fermeture
trap "kill $BACKEND_PID" EXIT
```

## ⚡ Scripts Automatisés (Recommandé)

Pour simplifier le processus, des scripts automatisés sont disponibles dans `build-scripts/` :

### Utilisation Rapide

**Développement quotidien :**
```bash
# Démarre backend + frontend automatiquement
./build-scripts/dev-start.sh
```

**Build complet avec nouveau backend :**
```bash
# Build automatique complet (PyInstaller + Electron + DMG)
./build-scripts/build-erudi.sh
```

**Mise à jour backend seulement :**
```bash
# Rebuild rapide du backend seulement
./build-scripts/quick-backend-rebuild.sh
cd frontend && npm run make
```

**Vérification du build :**
```bash
# Test et vérification automatique
./build-scripts/test-build.sh
```

### Avantages des Scripts
- ✅ **Automatisation complète** - Plus besoin de retenir les commandes
- ✅ **Vérifications intégrées** - Les scripts vérifient les prérequis
- ✅ **Gestion des erreurs** - Arrêt automatique en cas de problème
- ✅ **Feedback visuel** - Messages colorés pour suivre le progrès
- ✅ **Nettoyage automatique** - Gestion propre des processus

Voir `build-scripts/README.md` pour la documentation complète des scripts.

## 🐛 Dépannage

### Problème: Backend ne démarre pas
```bash
# Vérifier que l'exécutable existe et est bien copié
ls -la frontend/backend/backend
ls -la frontend/backend/_internal/

# Vérifier les logs
tail -f /tmp/erudi-backend.log
```

### Problème: Fenêtres multiples
- Vérifiée dans la dernière version du code avec les flags `isCreatingWindow` et `mainWindow`

### Problème: Variables d'environnement manquantes
```javascript
// Dans main.js, s'assurer que ces variables sont définies:
const backendEnv = {
  ...process.env,
  DATABASE_URL: "sqlite:///./data/erudi.db",
  CACHE_DIR: "./data/models_cache", 
  INDEXES_DIR: "./data/indexes"
};
```

## 📁 Structure du Projet Final

```
erudi/
├── README.md
├── backend/
│   ├── app/
│   ├── requirements.txt
│   ├── backend.spec
│   └── dist/backend/          # Build PyInstaller
│       ├── backend            # Exécutable
│       └── _internal/         # Dépendances
├── frontend/
│   ├── src/main.js           # Logique Electron principale
│   ├── forge.config.js       # Configuration build
│   ├── package.json
│   ├── backend/              # Copie du backend pour packaging
│   │   ├── backend
│   │   └── _internal/
│   └── out/make/             # Builds finaux
│       └── Erudi-Installer.dmg
└── build-scripts/
    ├── build-erudi.sh
    └── dev-start.sh
```

## 🔄 Workflow de Mise à Jour

1. **Modifier le code backend** dans `backend/app/`
2. **Rebuilder l'exécutable** avec `pyinstaller backend.spec`
3. **Copier le nouveau backend** vers `frontend/backend/`
4. **Rebuilder l'app Electron** avec `npm run make`
5. **Tester le nouveau DMG**

Cela permet de créer facilement des nouvelles versions avec des backends mis à jour!