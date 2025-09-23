#!/bin/bash

# Script de démonstration du workflow Erudi
# Montre comment utiliser les scripts pour un développement complet

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

echo -e "${PURPLE}🎬 Démonstration du Workflow Erudi${NC}"
echo -e "${BLUE}========================================${NC}"

echo -e "\n${YELLOW}📖 Ce script montre comment utiliser Erudi étape par étape${NC}"
echo -e "${YELLOW}📁 Projet: Application Electron avec backend Python intégré${NC}"

echo -e "\n${BLUE}🔧 Scripts disponibles:${NC}"
echo -e "  ${GREEN}dev-start.sh${NC}           - Démarrage développement"
echo -e "  ${GREEN}build-erudi.sh${NC}         - Build complet"
echo -e "  ${GREEN}quick-backend-rebuild.sh${NC} - Rebuild backend rapide"
echo -e "  ${GREEN}test-build.sh${NC}          - Tests et vérifications"

echo -e "\n${PURPLE}🚀 Workflows typiques:${NC}"

echo -e "\n${BLUE}1. Premier setup:${NC}"
echo -e "   cd backend && python -m venv venv && source venv/bin/activate"
echo -e "   pip install -r requirements.txt"
echo -e "   cd ../frontend && npm install"

echo -e "\n${BLUE}2. Développement quotidien:${NC}"
echo -e "   ./build-scripts/dev-start.sh    # ← Lance tout automatiquement"

echo -e "\n${BLUE}3. Après changement backend Python:${NC}"
echo -e "   ./build-scripts/quick-backend-rebuild.sh"
echo -e "   cd frontend && npm run make"

echo -e "\n${BLUE}4. Build complet pour distribution:${NC}"
echo -e "   ./build-scripts/build-erudi.sh  # ← Créé le DMG automatiquement"

echo -e "\n${BLUE}5. Vérification du build:${NC}"
echo -e "   ./build-scripts/test-build.sh   # ← Tests automatiques"

echo -e "\n${GREEN}📦 Résultat final:${NC}"
echo -e "   frontend/out/make/Erudi-Installer.dmg (≈300MB)"

echo -e "\n${YELLOW}💡 Conseils:${NC}"
echo -e "   • Utilisez toujours dev-start.sh pour le développement"
echo -e "   • Le build DMG contient tout (backend Python inclus)"
echo -e "   • Logs dans /tmp/erudi-backend.log pour debugging"
echo -e "   • Premier lancement macOS: autoriser dans Sécurité & Confidentialité"

echo -e "\n${PURPLE}✨ Votre build est prêt ! DMG disponible pour distribution.${NC}"

# Check current state
echo -e "\n${BLUE}📊 État actuel du projet:${NC}"
if [ -f "frontend/out/make/Erudi-Installer.dmg" ]; then
    DMG_SIZE=$(du -h "frontend/out/make/Erudi-Installer.dmg" | cut -f1)
    echo -e "   ${GREEN}✅ DMG build disponible ($DMG_SIZE)${NC}"
else
    echo -e "   ${YELLOW}⚠️  Pas de DMG - lancez ./build-scripts/build-erudi.sh${NC}"
fi

echo -e "\n${BLUE}📚 Documentation complète: README.md et build-scripts/README.md${NC}"