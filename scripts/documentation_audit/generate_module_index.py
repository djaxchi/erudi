#!/usr/bin/env python3
"""
Script pour générer l'index des modules Python publics.
Conforme aux guidelines Erudi et à l'étape 2 de la Phase 1 de documentation.
"""

import ast
import csv
from pathlib import Path
from typing import List, Dict, Any


def is_public_module(file_path: Path) -> bool:
    """
    Vérifie si un module est considéré comme public.
    
    Critères d'exclusion:
    - Fichiers commençant par _ (sauf __init__.py)
    - Fichiers dans des dossiers tests/
    - Fichiers __pycache__
    
    Args:
        file_path: Chemin vers le fichier Python
        
    Returns:
        True si le module est public, False sinon
    """
    # Exclure __pycache__
    if "__pycache__" in file_path.parts:
        return False
    
    # Exclure dossier tests
    if "tests" in file_path.parts:
        return False
    
    # Exclure fichiers commençant par _ sauf __init__.py
    if file_path.name.startswith("_") and file_path.name != "__init__.py":
        return False
    
    return True


def is_exported_in_init(module_file: Path, parent_init: Path) -> bool:
    """
    Vérifie si un module est exporté dans le __init__.py parent.
    
    Vérifie:
    - Présence dans __all__
    - Import direct (from .module import ...)
    
    Args:
        module_file: Fichier du module à vérifier
        parent_init: Fichier __init__.py parent
        
    Returns:
        True si exporté, False sinon
    """
    if not parent_init.exists():
        return False
    
    try:
        with open(parent_init, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Parser l'AST
        tree = ast.parse(content)
        
        module_name = module_file.stem
        
        # Vérifier __all__
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, (ast.List, ast.Tuple)):
                            all_items = [
                                elt.s for elt in node.value.elts
                                if isinstance(elt, ast.Constant)
                            ]
                            if module_name in all_items:
                                return True
            
            # Vérifier imports directs
            if isinstance(node, ast.ImportFrom):
                if node.module == f".{module_name}" or node.module == module_name:
                    return True
                # Vérifier from . import module_name
                if node.module in (".", None):
                    for alias in node.names:
                        if alias.name == module_name:
                            return True
        
        return False
        
    except Exception:
        # En cas d'erreur de parsing, considérer comme non exporté
        return False


def scan_python_modules(src_root: Path) -> List[Dict[str, Any]]:
    """
    Scan récursif de tous les modules Python publics.
    
    Args:
        src_root: Racine du répertoire src (backend/src)
        
    Returns:
        Liste de dictionnaires contenant les informations des modules
    """
    modules = []
    
    # Parcourir tous les fichiers Python
    for py_file in src_root.rglob("*.py"):
        # Vérifier si le module est public
        if not is_public_module(py_file):
            continue
        
        # Construire le chemin du module importable
        relative_path = py_file.relative_to(src_root.parent)
        
        # Convertir le chemin en nom de module
        module_parts = list(relative_path.parts[:-1])  # Exclure le fichier
        module_file = relative_path.stem
        
        # Pour __init__.py, le module est le package lui-même
        if module_file == "__init__":
            module_path = ".".join(module_parts)
        else:
            module_parts.append(module_file)
            module_path = ".".join(module_parts)
        
        # Vérifier la présence de __init__.py dans le package parent
        parent_dir = py_file.parent
        parent_init = parent_dir / "__init__.py"
        has_init = parent_init.exists()
        
        # Vérifier si exporté dans __init__.py (uniquement pour non-__init__.py)
        exported = False
        if module_file != "__init__" and has_init:
            exported = is_exported_in_init(py_file, parent_init)
        elif module_file == "__init__":
            # Les __init__.py sont considérés comme exportés par défaut
            exported = True
        
        # Déterminer si c'est un module public
        is_public = is_public_module(py_file) and (module_file == "__init__" or has_init)
        
        modules.append({
            "module_path": module_path,
            "file_path": str(relative_path),
            "package_root": "src",
            "is_public": is_public,
            "has_init": has_init,
            "exported_in_init": exported
        })
    
    return modules


def generate_csv(modules: List[Dict[str, Any]], output_path: Path) -> None:
    """
    Génère le fichier CSV avec l'index des modules.
    
    Args:
        modules: Liste des modules scannés
        output_path: Chemin du fichier CSV de sortie
    """
    # Trier par module_path pour cohérence
    modules_sorted = sorted(modules, key=lambda m: m["module_path"])
    
    # Vérifier les doublons
    module_paths = [m["module_path"] for m in modules_sorted]
    if len(module_paths) != len(set(module_paths)):
        print("⚠️  Warning: Doublons détectés dans module_path")
    
    # Créer le répertoire parent si nécessaire
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Écrire le CSV
    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = [
            "module_path",
            "file_path",
            "package_root",
            "is_public",
            "has_init",
            "exported_in_init"
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerows(modules_sorted)
    
    print(f"✅ module_index.csv généré: {output_path}")
    print(f"   - {len(modules_sorted)} modules indexés")
    print(f"   - {sum(1 for m in modules_sorted if m['is_public'])} modules publics")
    print(f"   - {sum(1 for m in modules_sorted if m['exported_in_init'])} modules exportés")


def main() -> None:
    """Point d'entrée principal du script."""
    # Définir les chemins
    project_root = Path(__file__).parent.parent.parent
    src_root = project_root / "backend" / "src"
    output_path = project_root / "reports" / "doc_audit" / "module_index.csv"
    
    print("🔍 Scan des modules Python dans backend/src/...")
    print(f"   Racine: {src_root}")
    
    # Scanner les modules
    modules = scan_python_modules(src_root)
    
    # Générer le CSV
    generate_csv(modules, output_path)
    
    print("\n✅ Étape 2 terminée avec succès!")


if __name__ == "__main__":
    main()
