#!/usr/bin/env python3
"""
Script pour générer le rapport de la Phase 2 (rédaction des docstrings).
"""

import json
import csv
import ast
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any


def has_docstring(node: ast.AST) -> bool:
    """Vérifie si un nœud AST a une docstring."""
    if not hasattr(node, "body") or not node.body:
        return False
    
    first_stmt = node.body[0]
    if isinstance(first_stmt, ast.Expr):
        if isinstance(first_stmt.value, ast.Constant):
            return isinstance(first_stmt.value.value, str)
        if isinstance(first_stmt.value, ast.Str):
            return True
    
    return False


def is_public_name(name: str) -> bool:
    """Vérifie si un nom est considéré comme public."""
    return not name.startswith("_") or name in ("__init__",)


def analyze_module(file_path: Path) -> Dict[str, Any]:
    """Analyse un module pour compter les docstrings présentes."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        
        tree = ast.parse(source, filename=str(file_path))
        
        stats = {
            "module": has_docstring(tree),
            "classes": 0,
            "functions": 0,
            "methods": 0
        }
        
        # Analyser les classes
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and is_public_name(node.name):
                if has_docstring(node):
                    stats["classes"] += 1
                
                # Méthodes
                for method_node in node.body:
                    if isinstance(method_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if is_public_name(method_node.name) or method_node.name == "__init__":
                            if has_docstring(method_node):
                                stats["methods"] += 1
        
        # Fonctions
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if is_public_name(node.name) and has_docstring(node):
                    stats["functions"] += 1
        
        return stats
        
    except Exception:
        return {"module": False, "classes": 0, "functions": 0, "methods": 0}


def main():
    project_root = Path(__file__).parent.parent.parent
    src_root = project_root / "backend" / "src"
    
    # Charger les données de Phase 1
    phase1_json = project_root / "reports" / "doc_audit" / "missing_docstrings.json"
    with open(phase1_json) as f:
        phase1_data = json.load(f)
    
    # Scanner les modules actuels
    print("🔍 Scan des docstrings actuelles...")
    
    files_touched = set()
    documented_now = {"modules": 0, "classes": 0, "functions": 0, "methods": 0}
    still_missing = {"modules": 0, "classes": 0, "functions": 0, "methods": 0}
    
    modules_completed = []
    modules_remaining = []
    
    for item in phase1_data["items"]:
        module_path = item["module_path"]
        file_path = src_root.parent / item["file_path"]
        
        # Analyser l'état actuel
        current_stats = analyze_module(file_path)
        
        # Compter les objets dans missing_docstrings
        missing = item["missing"]
        
        total_objects = {
            "module": 1,
            "classes": len(missing["classes"]),
            "functions": len(missing["functions"]),
            "methods": sum(len(c["methods"]) for c in missing["classes"])
        }
        
        # Calculer documented vs missing
        for key in ["classes", "functions", "methods"]:
            expected = total_objects[key]
            actual = current_stats[key]
            documented_now[key] += actual
            still_missing[key] += max(0, expected - actual)
        
        # Module docstring (cas spécial)
        if current_stats["module"]:
            documented_now["modules"] += 1
        else:
            still_missing["modules"] += 1
        
        # Déterminer si le module est "completed"
        missing_count = 0
        if missing["module_docstring"]:
            missing_count += 1
        for cls in missing["classes"]:
            if cls["missing"]:
                missing_count += 1
            missing_count += sum(1 for m in cls["methods"] if m["missing"])
        missing_count += sum(1 for f in missing["functions"] if f["missing"])
        
        # Vérifier si des docstrings ont été ajoutées
        has_improvements = (
            (missing["module_docstring"] and current_stats["module"]) or
            current_stats["classes"] > 0 or
            current_stats["functions"] > 0 or
            current_stats["methods"] > 0
        )
        
        if has_improvements:
            files_touched.add(str(file_path))
        
        if missing_count == 0:
            modules_completed.append(module_path)
        else:
            modules_remaining.append((module_path, missing_count))
    
    # Trier les modules restants
    modules_remaining.sort(key=lambda x: -x[1])
    
    # Générer phase2_summary.json
    summary = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "files_touched": len(files_touched),
        "modules_completed": len(modules_completed),
        "objects_documented": documented_now,
        "objects_remaining": still_missing,
        "total_objects": {
            "modules": phase1_data["summary"]["modules_total"],
            "classes": sum(len(item["missing"]["classes"]) for item in phase1_data["items"]),
            "functions": sum(len(item["missing"]["functions"]) for item in phase1_data["items"]),
            "methods": sum(sum(len(c["methods"]) for c in item["missing"]["classes"]) for item in phase1_data["items"])
        },
        "coverage_percent": {
            "modules": round(documented_now["modules"] / phase1_data["summary"]["modules_total"] * 100, 2) if phase1_data["summary"]["modules_total"] > 0 else 0,
            "overall": round(sum(documented_now.values()) / sum([
                phase1_data["summary"]["modules_total"],
                sum(len(item["missing"]["classes"]) for item in phase1_data["items"]),
                sum(len(item["missing"]["functions"]) for item in phase1_data["items"]),
                sum(sum(len(c["methods"]) for c in item["missing"]["classes"]) for item in phase1_data["items"])
            ]) * 100, 2)
        }
    }
    
    summary_path = project_root / "reports" / "doc_audit" / "phase2_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"✅ {summary_path}")
    
    # Générer phase2_run.log
    log_content = f"""=== Phase 2 - Rédaction des docstrings ===

Timestamp: {summary['timestamp']}

PROGRESSION:
------------
Fichiers modifiés: {summary['files_touched']}
Modules complétés: {summary['modules_completed']}

Objets documentés:
  - Modules: {documented_now['modules']}/{summary['total_objects']['modules']} ({summary['coverage_percent']['modules']}%)
  - Classes: {documented_now['classes']}/{summary['total_objects']['classes']}
  - Fonctions: {documented_now['functions']}/{summary['total_objects']['functions']}
  - Méthodes: {documented_now['methods']}/{summary['total_objects']['methods']}

Total documenté: {sum(documented_now.values())}/{sum(summary['total_objects'].values())} ({summary['coverage_percent']['overall']}%)

Objets restants:
  - Modules: {still_missing['modules']}
  - Classes: {still_missing['classes']}
  - Fonctions: {still_missing['functions']}
  - Méthodes: {still_missing['methods']}

Total restant: {sum(still_missing.values())}

TOP 10 MODULES RESTANT À DOCUMENTER:
------------------------------------
"""
    
    for i, (module, count) in enumerate(modules_remaining[:10], 1):
        log_content += f"{i:2d}. {module}: {count} docstrings manquantes\n"
    
    log_content += f"""

MODULES COMPLÉTÉS:
------------------
"""
    
    if modules_completed:
        for module in sorted(modules_completed):
            log_content += f"✅ {module}\n"
    else:
        log_content += "(aucun module complété pour le moment)\n"
    
    log_content += "\n=== Fin du rapport Phase 2 ===\n"
    
    log_path = project_root / "reports" / "doc_audit" / "phase2_run.log"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(log_content)
    
    print(f"✅ {log_path}")
    
    # Afficher résumé
    print(f"\n📊 Résumé Phase 2:")
    print(f"   Fichiers touchés: {summary['files_touched']}")
    print(f"   Modules complétés: {summary['modules_completed']}")
    print(f"   Couverture globale: {summary['coverage_percent']['overall']}%")
    print(f"   Modules restants: {len(modules_remaining)}")


if __name__ == "__main__":
    main()
