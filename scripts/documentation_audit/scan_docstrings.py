#!/usr/bin/env python3
"""
Script pour scanner la présence des docstrings dans les modules Python.
Conforme aux guidelines Erudi et à l'étape 3 de la Phase 1 de documentation.
"""

import ast
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


def is_public_name(name: str) -> bool:
    """
    Vérifie si un nom est considéré comme public.
    
    Args:
        name: Nom à vérifier
        
    Returns:
        True si public (ne commence pas par _), False sinon
    """
    return not name.startswith("_") or name in ("__init__",)


def has_docstring(node: ast.AST) -> bool:
    """
    Vérifie si un nœud AST a une docstring.
    
    Args:
        node: Nœud AST (Module, ClassDef, FunctionDef, AsyncFunctionDef)
        
    Returns:
        True si une docstring est présente, False sinon
    """
    if not hasattr(node, "body") or not node.body:
        return False
    
    first_stmt = node.body[0]
    
    # Python 3.7+ : ast.Constant
    if isinstance(first_stmt, ast.Expr):
        if isinstance(first_stmt.value, ast.Constant):
            return isinstance(first_stmt.value.value, str)
        # Python 3.6 fallback : ast.Str
        if isinstance(first_stmt.value, ast.Str):
            return True
    
    return False


def analyze_class(class_node: ast.ClassDef) -> Dict[str, Any]:
    """
    Analyse une classe pour détecter les docstrings manquantes.
    
    Args:
        class_node: Nœud AST de la classe
        
    Returns:
        Dictionnaire avec nom, présence docstring et méthodes
    """
    class_info = {
        "name": class_node.name,
        "missing": not has_docstring(class_node),
        "methods": []
    }
    
    # Analyser les méthodes
    for node in class_node.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Considérer __init__ comme public si la classe est publique
            if is_public_name(node.name) or node.name == "__init__":
                method_info = {
                    "name": node.name,
                    "missing": not has_docstring(node)
                }
                class_info["methods"].append(method_info)
    
    return class_info


def analyze_module(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Analyse un module Python pour détecter les docstrings manquantes.
    
    Args:
        file_path: Chemin du fichier Python
        
    Returns:
        Dictionnaire avec les informations du module ou None en cas d'erreur
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        
        tree = ast.parse(source, filename=str(file_path))
        
        # Vérifier docstring du module
        module_has_docstring = has_docstring(tree)
        
        # Analyser les classes publiques
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Vérifier si c'est une classe de niveau module (pas imbriquée)
                if is_public_name(node.name):
                    # Vérifier que la classe est au niveau module
                    for child in tree.body:
                        if child == node:
                            classes.append(analyze_class(node))
                            break
        
        # Analyser les fonctions publiques de niveau module
        functions = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if is_public_name(node.name):
                    func_info = {
                        "name": node.name,
                        "missing": not has_docstring(node)
                    }
                    functions.append(func_info)
        
        return {
            "module_docstring": not module_has_docstring,
            "classes": classes,
            "functions": functions
        }
        
    except Exception as e:
        print(f"⚠️  Erreur lors de l'analyse de {file_path}: {e}")
        return None


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
            # Ne scanner que les modules publics
            if row["is_public"] == "True":
                modules.append(row)
    
    return modules


def scan_all_modules(src_root: Path, modules: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Scanne tous les modules pour détecter les docstrings manquantes.
    
    Args:
        src_root: Racine du projet (contient backend/)
        modules: Liste des modules depuis module_index.csv
        
    Returns:
        Liste des résultats d'analyse
    """
    results = []
    
    print(f"🔍 Scan de {len(modules)} modules publics...")
    
    for idx, module in enumerate(modules, 1):
        module_path = module["module_path"]
        file_path = src_root / "backend" / module["file_path"]
        
        print(f"   [{idx}/{len(modules)}] {module_path}")
        
        analysis = analyze_module(file_path)
        
        if analysis:
            results.append({
                "module_path": module_path,
                "file_path": str(Path("backend") / module["file_path"]),
                "missing": analysis
            })
    
    return results


def calculate_summary(results: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Calcule les statistiques récapitulatives.
    
    Args:
        results: Liste des résultats d'analyse
        
    Returns:
        Dictionnaire avec les totaux
    """
    modules_total = len(results)
    public_objects_total = 0
    missing_total = 0
    
    for result in results:
        missing = result["missing"]
        
        # Compter docstring de module
        public_objects_total += 1
        if missing["module_docstring"]:
            missing_total += 1
        
        # Compter classes
        for cls in missing["classes"]:
            public_objects_total += 1
            if cls["missing"]:
                missing_total += 1
            
            # Compter méthodes
            for method in cls["methods"]:
                public_objects_total += 1
                if method["missing"]:
                    missing_total += 1
        
        # Compter fonctions
        for func in missing["functions"]:
            public_objects_total += 1
            if func["missing"]:
                missing_total += 1
    
    return {
        "modules_total": modules_total,
        "public_objects_total": public_objects_total,
        "missing_total": missing_total,
        "coverage_percent": round(
            ((public_objects_total - missing_total) / public_objects_total * 100)
            if public_objects_total > 0 else 0,
            2
        )
    }


def generate_json_report(results: List[Dict[str, Any]], output_path: Path) -> Dict[str, int]:
    """
    Génère le rapport JSON des docstrings manquantes.
    
    Args:
        results: Liste des résultats d'analyse
        output_path: Chemin du fichier JSON de sortie
        
    Returns:
        Statistiques récapitulatives
    """
    summary = calculate_summary(results)
    
    report = {
        "summary": summary,
        "items": results
    }
    
    # Créer le répertoire parent si nécessaire
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Écrire le JSON
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ missing_docstrings.json généré: {output_path}")
    print(f"   - {summary['modules_total']} modules scannés")
    print(f"   - {summary['public_objects_total']} objets publics")
    print(f"   - {summary['missing_total']} docstrings manquantes")
    print(f"   - {summary['coverage_percent']}% de couverture")
    
    return summary


def write_run_log(log_path: Path, summary: Dict[str, int], duration: float) -> None:
    """
    Écrit le journal d'exécution.
    
    Args:
        log_path: Chemin du fichier de log
        summary: Statistiques récapitulatives
        duration: Durée d'exécution en secondes
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    log_content = f"""=== Erudi Documentation Audit - Scan des Docstrings ===

Timestamp: {timestamp}
Durée d'exécution: {duration:.2f}s

RÉSULTATS:
----------
Modules scannés: {summary['modules_total']}
Objets publics totaux: {summary['public_objects_total']}
Docstrings manquantes: {summary['missing_total']}
Couverture: {summary['coverage_percent']}%

DÉTAIL:
-------
- Modules: Tous les fichiers .py publics sous backend/src/
- Objets publics: Classes, fonctions, méthodes (nom ne commençant pas par _)
- Méthodes __init__: Considérées comme publiques si la classe est publique

FICHIERS GÉNÉRÉS:
-----------------
- reports/doc_audit/missing_docstrings.json
- reports/doc_audit/run.log (ce fichier)

PROCHAINES ÉTAPES:
------------------
- Analyser les modules avec le plus de docstrings manquantes
- Prioriser la documentation des points d'entrée (API, services)
- Établir un plan de documentation systématique

===================================================
"""
    
    # Créer le répertoire parent si nécessaire
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(log_content)
    
    print(f"✅ run.log généré: {log_path}")


def main() -> None:
    """Point d'entrée principal du script."""
    start_time = datetime.now()
    
    # Définir les chemins
    project_root = Path(__file__).parent.parent.parent
    index_path = project_root / "reports" / "doc_audit" / "module_index.csv"
    output_json = project_root / "reports" / "doc_audit" / "missing_docstrings.json"
    output_log = project_root / "reports" / "doc_audit" / "run.log"
    
    print("🔍 Scan des docstrings dans backend/src/...")
    
    # Charger l'index des modules
    modules = load_module_index(index_path)
    
    # Scanner tous les modules
    results = scan_all_modules(project_root, modules)
    
    # Générer le rapport JSON
    summary = generate_json_report(results, output_json)
    
    # Calculer la durée
    duration = (datetime.now() - start_time).total_seconds()
    
    # Écrire le log
    write_run_log(output_log, summary, duration)
    
    print("\n✅ Étape 3 terminée avec succès!")


if __name__ == "__main__":
    main()
