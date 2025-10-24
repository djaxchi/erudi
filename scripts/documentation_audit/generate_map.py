#!/usr/bin/env python3
"""
Script pour générer la map docs↔code (docs/map.yaml).
Conforme aux guidelines Erudi et à l'étape 4 de la Phase 1 de documentation.
"""

import csv
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set


def load_module_index(index_path: Path) -> List[Dict[str, str]]:
    """
    Charge l'index des modules depuis le CSV.
    
    Args:
        index_path: Chemin du fichier module_index.csv
        
    Returns:
        Liste des modules indexés
    """
    modules = []
    
    with open(index_path, "r", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            modules.append(row)
    
    return modules


def is_user_facing_module(module_path: str, file_path: str) -> bool:
    """
    Détermine si un module est pertinent pour l'utilisateur final.
    
    Critères d'exclusion:
    - Modules __init__.py (sauf domaines principaux)
    - Utilitaires internes (utils/ non exportés)
    - Modules privés ou de test
    
    Args:
        module_path: Chemin du module (ex: src.engines.mlx_engine)
        file_path: Chemin du fichier (ex: src/engines/mlx_engine.py)
        
    Returns:
        True si le module est pertinent pour la documentation
    """
    # Exclure les __init__.py sauf pour les packages principaux
    if file_path.endswith("__init__.py"):
        # Garder uniquement les __init__ de niveau domaine
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
    
    # Exclure les utilitaires internes non critiques
    if ".utils." in module_path or module_path.endswith(".utils"):
        return False
    
    # Exclure les modules de repository (détails d'implémentation)
    if ".repository" in module_path:
        return False
    
    return True


def categorize_modules(modules: List[Dict[str, str]]) -> Dict[str, List[str]]:
    """
    Organise les modules par catégories fonctionnelles.
    
    Args:
        modules: Liste des modules depuis module_index.csv
        
    Returns:
        Dictionnaire catégorie -> liste de modules
    """
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
        
        # Ne garder que les modules publics et pertinents
        if not is_public or not is_user_facing_module(module_path, file_path):
            continue
        
        # Catégoriser
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
    
    # Supprimer les catégories vides
    categories = {k: v for k, v in categories.items() if v}
    
    # Trier les modules dans chaque catégorie
    for category in categories:
        categories[category].sort()
    
    return categories


def generate_map_yaml(categories: Dict[str, List[str]], output_path: Path) -> None:
    """
    Génère le fichier docs/map.yaml.
    
    Args:
        categories: Dictionnaire catégorie -> liste de modules
        output_path: Chemin du fichier YAML de sortie
    """
    # Construire la structure YAML
    doc_map = {
        "# Erudi Documentation Map": None,
        "# Maps code modules to documentation reference pages": None,
        "# Generated automatically - do not edit manually": None,
        "": None,
        "reference": categories
    }
    
    # Créer le répertoire parent si nécessaire
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Écrire le YAML avec un format propre
    with open(output_path, "w", encoding="utf-8") as f:
        # Écrire les commentaires manuellement pour un meilleur format
        f.write("# Erudi Documentation Map\n")
        f.write("# Maps code modules to documentation reference pages\n")
        f.write("# Generated automatically - do not edit manually\n")
        f.write(f"# Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Écrire la structure reference
        f.write("reference:\n")
        for category, modules in categories.items():
            f.write(f"  {category}:\n")
            for module in modules:
                f.write(f"    - {module}\n")
            f.write("\n")
    
    print(f"✅ map.yaml généré: {output_path}")
    print(f"   - {len(categories)} catégories")
    print(f"   - {sum(len(mods) for mods in categories.values())} modules référencés")


def validate_map(
    categories: Dict[str, List[str]],
    all_modules: List[Dict[str, str]],
    log_path: Path
) -> None:
    """
    Valide que tous les modules de la map existent dans module_index.csv.
    
    Args:
        categories: Dictionnaire catégorie -> liste de modules
        all_modules: Liste complète des modules depuis module_index.csv
        log_path: Chemin du fichier de log
    """
    # Construire un set de tous les module_path valides
    valid_modules = {m["module_path"] for m in all_modules}
    
    # Construire un set de tous les modules dans la map
    map_modules: Set[str] = set()
    for modules in categories.values():
        map_modules.update(modules)
    
    # Vérifier les modules manquants (dans la map mais pas dans l'index)
    missing_modules = map_modules - valid_modules
    
    # Vérifier les doublons
    all_map_modules = []
    for modules in categories.values():
        all_map_modules.extend(modules)
    duplicates = [m for m in map_modules if all_map_modules.count(m) > 1]
    
    # Reporter dans le log
    validation_report = f"""

=== Validation de docs/map.yaml ===

Modules dans la map: {len(map_modules)}
Modules valides dans l'index: {len(valid_modules)}

"""
    
    if missing_modules:
        validation_report += f"⚠️  ATTENTION: {len(missing_modules)} module(s) manquant(s) dans module_index.csv:\n"
        for module in sorted(missing_modules):
            validation_report += f"   - {module}\n"
        validation_report += "\n"
    else:
        validation_report += "✅ Tous les modules de la map existent dans module_index.csv\n\n"
    
    if duplicates:
        validation_report += f"⚠️  ATTENTION: {len(duplicates)} doublon(s) détecté(s):\n"
        for module in sorted(duplicates):
            validation_report += f"   - {module}\n"
        validation_report += "\n"
    else:
        validation_report += "✅ Aucun doublon détecté\n\n"
    
    # Distribution par catégorie
    validation_report += "Distribution par catégorie:\n"
    for category, modules in sorted(categories.items()):
        validation_report += f"   - {category}: {len(modules)} module(s)\n"
    
    validation_report += "\n=== Fin de validation ===\n"
    
    # Ajouter au log existant
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(validation_report)
    
    print("\n✅ Validation terminée et ajoutée à run.log")
    
    if missing_modules:
        print(f"⚠️  {len(missing_modules)} module(s) manquant(s) - voir run.log")
    if duplicates:
        print(f"⚠️  {len(duplicates)} doublon(s) détecté(s) - voir run.log")


def main() -> None:
    """Point d'entrée principal du script."""
    # Définir les chemins
    project_root = Path(__file__).parent.parent.parent
    index_path = project_root / "reports" / "doc_audit" / "module_index.csv"
    output_yaml = project_root / "docs" / "map.yaml"
    log_path = project_root / "reports" / "doc_audit" / "run.log"
    
    print("🔍 Construction de la map docs↔code...")
    
    # Charger l'index des modules
    modules = load_module_index(index_path)
    print(f"   - {len(modules)} modules dans l'index")
    
    # Catégoriser les modules
    categories = categorize_modules(modules)
    print(f"   - {len(categories)} catégories identifiées")
    
    # Générer le YAML
    generate_map_yaml(categories, output_yaml)
    
    # Valider et reporter
    validate_map(categories, modules, log_path)
    
    print("\n✅ Étape 4 terminée avec succès!")


if __name__ == "__main__":
    main()
