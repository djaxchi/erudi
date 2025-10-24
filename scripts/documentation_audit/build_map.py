#!/usr/bin/env python3
"""
Script utilitaire pour construire la map docs↔code (docs/map.yaml).

Usage:
    python tools/docs/build_map.py --index reports/doc_audit/module_index.csv --out docs/map.yaml

Requirements:
    Python 3.9+

Exit codes:
    0: Succès
    1: Erreur d'arguments
    2: Erreur de traitement
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def is_user_facing_module(module_path: str, file_path: str) -> bool:
    """Détermine si un module est pertinent pour l'utilisateur final."""
    if file_path.endswith("__init__.py"):
        important_packages = [
            "src/__init__.py",
            "src/core/__init__.py",
            "src/engines/__init__.py",
            "src/domains/__init__.py",
            "src/entities/__init__.py",
            "src/database/__init__.py",
        ]
        if file_path not in important_packages:
            return False
    
    if ".utils." in module_path or module_path.endswith(".utils"):
        return False
    
    if ".repository" in module_path:
        return False
    
    return True


def categorize_modules(modules: List[Dict[str, str]]) -> Dict[str, List[str]]:
    """Organise les modules par catégories fonctionnelles."""
    categories: Dict[str, List[str]] = {
        "core": [],
        "engines": [],
        "conversations": [],
        "llms": [],
        "knowledge_base": [],
        "training": [],
        "arena": [],
        "hardware": [],
        "entities": [],
        "database": [],
    }
    
    for module in modules:
        module_path = module["module_path"]
        file_path = module["file_path"]
        is_public = module["is_public"] == "True"
        
        if not is_public or not is_user_facing_module(module_path, file_path):
            continue
        
        if "engines" in module_path:
            categories["engines"].append(module_path)
        elif "conversations" in module_path:
            categories["conversations"].append(module_path)
        elif "llms" in module_path:
            categories["llms"].append(module_path)
        elif "knowledge_base" in module_path:
            categories["knowledge_base"].append(module_path)
        elif "training" in module_path:
            categories["training"].append(module_path)
        elif "arena" in module_path:
            categories["arena"].append(module_path)
        elif "hardware" in module_path:
            categories["hardware"].append(module_path)
        elif "entities" in module_path:
            categories["entities"].append(module_path)
        elif "database" in module_path:
            categories["database"].append(module_path)
        elif "core" in module_path:
            categories["core"].append(module_path)
    
    categories = {k: v for k, v in categories.items() if v}
    
    for category in categories:
        categories[category].sort()
    
    return categories


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Construire la map docs↔code (docs/map.yaml)."
    )
    parser.add_argument(
        "--index",
        required=True,
        type=Path,
        help="Chemin vers module_index.csv"
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Chemin de sortie pour map.yaml"
    )
    
    args = parser.parse_args()
    
    # Validation des arguments
    if not args.index.exists():
        print(f"❌ Erreur: Le fichier index n'existe pas: {args.index}", file=sys.stderr)
        return 1
    
    if not args.index.is_file():
        print(f"❌ Erreur: Le chemin index n'est pas un fichier: {args.index}", file=sys.stderr)
        return 1
    
    try:
        print(f"🔍 Construction de la map depuis {args.index}...")
        
        # Charger l'index
        with open(args.index, "r", encoding="utf-8") as csvfile:
            modules = list(csv.DictReader(csvfile))
        
        print(f"   - {len(modules)} modules dans l'index")
        
        # Catégoriser
        categories = categorize_modules(modules)
        total_modules = sum(len(mods) for mods in categories.values())
        
        print(f"   - {len(categories)} catégories identifiées")
        print(f"   - {total_modules} modules sélectionnés")
        
        # Créer le répertoire parent si nécessaire
        args.out.parent.mkdir(parents=True, exist_ok=True)
        
        # Écrire le YAML
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("# Erudi Documentation Map\n")
            f.write("# Maps code modules to documentation reference pages\n")
            f.write("# Generated automatically - do not edit manually\n")
            f.write(f"# Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("reference:\n")
            for category, modules in categories.items():
                f.write(f"  {category}:\n")
                for module in modules:
                    f.write(f"    - {module}\n")
                f.write("\n")
        
        print(f"✅ {args.out}")
        print(f"   - {len(categories)} catégories")
        print(f"   - {total_modules} modules référencés")
        
        # Afficher la distribution
        print("\n📊 Distribution par catégorie:")
        for category, mods in sorted(categories.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"   - {category}: {len(mods)}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Erreur: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
