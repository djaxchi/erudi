# 🚀 Erudi - Guide de Démarrage Rapide

## Démarrage Ultra-Rapide

```bash
# 1. Setup initial (une seule fois)
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cd ../frontend && npm install

# 2. Développement quotidien 
./build-scripts/dev-start.sh

# 3. Build pour distribution
./build-scripts/build-erudi.sh
```

## 🎯 Utilisation des Scripts

| Script | Usage | Durée |
|--------|-------|-------|
| `dev-start.sh` | Développement quotidien | 10s |
| `build-erudi.sh` | Build complet DMG | 3-5min |
| `quick-backend-rebuild.sh` | Rebuild backend seul | 30s |
| `test-build.sh` | Vérifications | 5s |
| `demo.sh` | Aide et documentation | - |

## 📦 Résultat

✅ **DMG prêt à distribuer** : `frontend/out/make/Erudi-Installer.dmg` (~300MB)  
✅ **App autonome** : Backend Python intégré, aucune dépendance externe  
✅ **Compatible macOS** : ARM64 + Intel, avec gestion Gatekeeper  

## 📚 Documentation Complète

- **README.md** - Documentation technique complète
- **build-scripts/README.md** - Guide détaillé des scripts

---

**🎉 Votre application Electron avec backend Python est prête !**