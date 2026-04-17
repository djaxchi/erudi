#!/usr/bin/env python3
"""
Script utilitaire pour scanner les modules Python et générer les rapports de documentation.
Génère module_index.csv et missing_docstrings.json.

Usage:
    python tools/docs/scan_modules.py --src backend/src --out reports/doc_audit

Requirements:
    Python 3.9+

Exit codes:
    0: Succès
    1: Erreur d'arguments
    2: Erreur de traitement
"""

import argparse
import ast
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


def is_public_module(file_path: Path) -> bool:
    """Vérifie si un module est considéré comme public."""
    if "__pycache__" in file_path.parts:
        return False
    if "tests" in file_path.parts:
        return False
    if file_path.name.startswith("_") and file_path.name != "__init__.py":
        return False
    return True


def is_exported_in_init(module_file: Path, parent_init: Path) -> bool:
    """Vérifie si un module est exporté dans le __init__.py parent."""
    if not parent_init.exists():
        return False
    
    try:
        with open(parent_init, "r", encoding="utf-8") as f:
            content = f.read()
        
        tree = ast.parse(content)
        module_name = module_file.stem
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, (ast.List, ast.Tuple)):
                            all_items = [
                                elt.s if hasattr(elt, 's') else elt.value
                                for elt in node.value.elts
                                if isinstance(elt, (ast.Str, ast.Constant))
                            ]
                            if module_name in all_items:
                                return True
            
            if isinstance(node, ast.ImportFrom):
                if node.module == f".{module_name}" or node.module == module_name:
                    return True
                if node.module in (".", None):
                    for alias in node.names:
                        if alias.name == module_name:
                            return True
        
        return False
    except Exception:
        return False


def scan_python_modules(src_root: Path) -> List[Dict[str, Any]]:
    """Scan récursif de tous les modules Python publics."""
    modules = []
    
    for py_file in src_root.rglob("*.py"):
        if not is_public_module(py_file):
            continue
        
        relative_path = py_file.relative_to(src_root.parent)
        module_parts = list(relative_path.parts[:-1])
        module_file = relative_path.stem
        
        if module_file == "__init__":
            module_path = ".".join(module_parts)
        else:
            module_parts.append(module_file)
            module_path = ".".join(module_parts)
        
        parent_dir = py_file.parent
        parent_init = parent_dir / "__init__.py"
        has_init = parent_init.exists()
        
        exported = False
        if module_file != "__init__" and has_init:
            exported = is_exported_in_init(py_file, parent_init)
        elif module_file == "__init__":
            exported = True
        
        is_public = is_public_module(py_file) and (module_file == "__init__" or has_init)
        
        modules.append({
            "module_path": module_path,
            "file_path": str(relative_path),
            "package_root": relative_path.parts[0],
            "is_public": is_public,
            "has_init": has_init,
            "exported_in_init": exported
        })
    
    return modules


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


def analyze_class(class_node: ast.ClassDef) -> Dict[str, Any]:
    """Analyse une classe pour détecter les docstrings manquantes."""
    class_info = {
        "name": class_node.name,
        "missing": not has_docstring(class_node),
        "methods": []
    }
    
    for node in class_node.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if is_public_name(node.name) or node.name == "__init__":
                method_info = {
                    "name": node.name,
                    "missing": not has_docstring(node)
                }
                class_info["methods"].append(method_info)
    
    return class_info


def analyze_module(file_path: Path) -> Optional[Dict[str, Any]]:
    """Analyse un module Python pour détecter les docstrings manquantes."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        
        tree = ast.parse(source, filename=str(file_path))
        module_has_docstring = has_docstring(tree)
        
        classes = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                if is_public_name(node.name):
                    classes.append(analyze_class(node))
        
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
        print(f"⚠️  Erreur lors de l'analyse de {file_path}: {e}", file=sys.stderr)
        return None


def calculate_summary(results: List[Dict[str, Any]]) -> Dict[str, int]:
    """Calcule les statistiques récapitulatives."""
    modules_total = len(results)
    public_objects_total = 0
    missing_total = 0
    
    for result in results:
        missing = result["missing"]
        
        public_objects_total += 1
        if missing["module_docstring"]:
            missing_total += 1
        
        for cls in missing["classes"]:
            public_objects_total += 1
            if cls["missing"]:
                missing_total += 1
            
            for method in cls["methods"]:
                public_objects_total += 1
                if method["missing"]:
                    missing_total += 1
        
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


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Scanner les modules Python et générer les rapports de documentation."
    )
    parser.add_argument(
        "--src",
        required=True,
        type=Path,
        help="Chemin vers le répertoire source (ex: backend/src)"
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Chemin vers le répertoire de sortie (ex: reports/doc_audit)"
    )
    
    args = parser.parse_args()
    
    # Validation des arguments
    if not args.src.exists():
        print(f"❌ Erreur: Le répertoire source n'existe pas: {args.src}", file=sys.stderr)
        return 1
    
    if not args.src.is_dir():
        print(f"❌ Erreur: Le chemin source n'est pas un répertoire: {args.src}", file=sys.stderr)
        return 1
    
    # Créer le répertoire de sortie si nécessaire
    args.out.mkdir(parents=True, exist_ok=True)
    
    try:
        print(f"🔍 Scan des modules dans {args.src}...")
        
        # Scanner les modules
        modules = scan_python_modules(args.src)
        public_modules = [m for m in modules if m["is_public"]]
        
        # Générer module_index.csv
        index_path = args.out / "module_index.csv"
        modules_sorted = sorted(modules, key=lambda m: m["module_path"])
        
        with open(index_path, "w", newline="", encoding="utf-8") as csvfile:
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
        
        print(f"✅ {index_path}")
        print(f"   - {len(modules)} modules indexés")
        print(f"   - {len(public_modules)} modules publics")
        
        # Scanner les docstrings
        print(f"\n🔍 Scan des docstrings...")
        
        results = []
        for module in public_modules:
            file_path = args.src.parent / module["file_path"]
            analysis = analyze_module(file_path)
            
            if analysis:
                results.append({
                    "module_path": module["module_path"],
                    "file_path": module["file_path"],
                    "missing": analysis
                })
        
        # Générer missing_docstrings.json
        summary = calculate_summary(results)
        report = {
            "summary": summary,
            "items": results
        }
        
        json_path = args.out / "missing_docstrings.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"✅ {json_path}")
        print(f"   - {summary['modules_total']} modules scannés")
        print(f"   - {summary['missing_total']} docstrings manquantes")
        print(f"   - {summary['coverage_percent']}% de couverture")
        
        return 0
        
    except Exception as e:
        print(f"❌ Erreur: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
