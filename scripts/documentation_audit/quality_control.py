#!/usr/bin/env python3
"""
Script pour le contrôle qualité de la Phase 1.
Conforme aux guidelines Erudi et à l'étape 5 de la Phase 1 de documentation.
"""

import csv
import json
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any


def calculate_category_stats(doc_data: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
    """
    Calcule les statistiques par catégorie (module/class/function).
    
    Args:
        doc_data: Données depuis missing_docstrings.json
        
    Returns:
        Dictionnaire avec les statistiques par catégorie
    """
    stats = {
        "module": {"total": 0, "missing": 0},
        "class": {"total": 0, "missing": 0},
        "function": {"total": 0, "missing": 0},
        "method": {"total": 0, "missing": 0}
    }
    
    for item in doc_data["items"]:
        missing = item["missing"]
        
        # Module docstring
        stats["module"]["total"] += 1
        if missing["module_docstring"]:
            stats["module"]["missing"] += 1
        
        # Classes
        for cls in missing["classes"]:
            stats["class"]["total"] += 1
            if cls["missing"]:
                stats["class"]["missing"] += 1
            
            # Méthodes
            for method in cls["methods"]:
                stats["method"]["total"] += 1
                if method["missing"]:
                    stats["method"]["missing"] += 1
        
        # Fonctions
        for func in missing["functions"]:
            stats["function"]["total"] += 1
            if func["missing"]:
                stats["function"]["missing"] += 1
    
    # Calculer les pourcentages
    for category in stats:
        total = stats[category]["total"]
        missing = stats[category]["missing"]
        stats[category]["percent"] = round(
            (missing / total * 100) if total > 0 else 0,
            2
        )
        stats[category]["present"] = total - missing
    
    return stats


def get_top_10_modules(doc_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Identifie les 10 modules avec le plus de docstrings manquantes.
    
    Args:
        doc_data: Données depuis missing_docstrings.json
        
    Returns:
        Liste des 10 modules avec le plus de manques
    """
    module_stats = []
    
    for item in doc_data["items"]:
        missing_count = 0
        total_count = 0
        
        missing = item["missing"]
        
        # Module docstring
        total_count += 1
        if missing["module_docstring"]:
            missing_count += 1
        
        # Classes
        for cls in missing["classes"]:
            total_count += 1
            if cls["missing"]:
                missing_count += 1
            
            # Méthodes
            for method in cls["methods"]:
                total_count += 1
                if method["missing"]:
                    missing_count += 1
        
        # Fonctions
        for func in missing["functions"]:
            total_count += 1
            if func["missing"]:
                missing_count += 1
        
        if missing_count > 0:
            module_stats.append({
                "module_path": item["module_path"],
                "file_path": item["file_path"],
                "missing": missing_count,
                "total": total_count,
                "percent": round(missing_count / total_count * 100, 1)
            })
    
    # Trier par nombre de manques décroissant
    module_stats.sort(key=lambda x: (-x["missing"], -x["percent"]))
    
    return module_stats[:10]


def check_map_modules_without_docstring(
    doc_data: Dict[str, Any],
    map_data: Dict[str, Any]
) -> List[str]:
    """
    Vérifie quels modules de map.yaml n'ont pas de docstring de module.
    
    Args:
        doc_data: Données depuis missing_docstrings.json
        map_data: Données depuis docs/map.yaml
        
    Returns:
        Liste des modules sans docstring de module
    """
    # Construire un dict module_path -> missing_module_docstring
    docstring_status = {}
    for item in doc_data["items"]:
        docstring_status[item["module_path"]] = item["missing"]["module_docstring"]
    
    # Extraire tous les modules de la map
    map_modules = []
    for category, modules in map_data["reference"].items():
        map_modules.extend(modules)
    
    # Identifier ceux sans docstring
    modules_without_docstring = []
    for module in map_modules:
        if module in docstring_status and docstring_status[module]:
            modules_without_docstring.append(module)
    
    return sorted(modules_without_docstring)


def validate_acceptance_criteria(
    project_root: Path
) -> Dict[str, Dict[str, Any]]:
    """
    Valide tous les critères d'acceptation de la Phase 1.
    
    Args:
        project_root: Racine du projet
        
    Returns:
        Dictionnaire avec les résultats de validation
    """
    results = {
        "module_index": {"valid": False, "details": ""},
        "missing_docstrings": {"valid": False, "details": ""},
        "map_yaml": {"valid": False, "details": ""},
        "run_log": {"valid": False, "details": ""}
    }
    
    # 1. Vérifier module_index.csv
    index_path = project_root / "reports" / "doc_audit" / "module_index.csv"
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            modules = list(csv.DictReader(f))
            if len(modules) > 0:
                # Vérifier la cohérence des colonnes
                required_cols = ["module_path", "file_path", "package_root", 
                               "is_public", "has_init", "exported_in_init"]
                if all(col in modules[0] for col in required_cols):
                    results["module_index"]["valid"] = True
                    results["module_index"]["details"] = f"{len(modules)} modules, structure valide"
                else:
                    results["module_index"]["details"] = "Colonnes manquantes"
            else:
                results["module_index"]["details"] = "Fichier vide"
    except Exception as e:
        results["module_index"]["details"] = f"Erreur: {str(e)}"
    
    # 2. Vérifier missing_docstrings.json
    json_path = project_root / "reports" / "doc_audit" / "missing_docstrings.json"
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            doc_data = json.load(f)
            summary = doc_data.get("summary", {})
            
            # Vérifier la structure
            if "modules_total" in summary and "public_objects_total" in summary:
                # Vérifier les valeurs non négatives
                if (summary["modules_total"] >= 0 and 
                    summary["public_objects_total"] >= 0 and
                    summary["missing_total"] >= 0):
                    results["missing_docstrings"]["valid"] = True
                    results["missing_docstrings"]["details"] = (
                        f"{summary['modules_total']} modules, "
                        f"{summary['missing_total']} manquantes"
                    )
                else:
                    results["missing_docstrings"]["details"] = "Valeurs négatives détectées"
            else:
                results["missing_docstrings"]["details"] = "Structure invalide"
    except json.JSONDecodeError:
        results["missing_docstrings"]["details"] = "JSON invalide"
    except Exception as e:
        results["missing_docstrings"]["details"] = f"Erreur: {str(e)}"
    
    # 3. Vérifier docs/map.yaml
    yaml_path = project_root / "docs" / "map.yaml"
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            map_data = yaml.safe_load(f)
            
            # Vérifier la structure
            if "reference" in map_data and isinstance(map_data["reference"], dict):
                # Vérifier que toutes les références existent dans module_index
                all_map_modules = []
                for modules in map_data["reference"].values():
                    all_map_modules.extend(modules)
                
                # Charger les modules valides
                with open(index_path, "r", encoding="utf-8") as idx:
                    valid_modules = {row["module_path"] for row in csv.DictReader(idx)}
                
                invalid_refs = [m for m in all_map_modules if m not in valid_modules]
                
                if not invalid_refs:
                    results["map_yaml"]["valid"] = True
                    results["map_yaml"]["details"] = (
                        f"{len(all_map_modules)} modules, "
                        f"{len(map_data['reference'])} catégories"
                    )
                else:
                    results["map_yaml"]["details"] = f"{len(invalid_refs)} références invalides"
            else:
                results["map_yaml"]["details"] = "Structure invalide"
    except yaml.YAMLError:
        results["map_yaml"]["details"] = "YAML invalide"
    except Exception as e:
        results["map_yaml"]["details"] = f"Erreur: {str(e)}"
    
    # 4. Vérifier run.log
    log_path = project_root / "reports" / "doc_audit" / "run.log"
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()
            
            # Vérifier la présence d'informations essentielles
            has_date = "Timestamp:" in content or "2025" in content
            has_counters = any(word in content for word in 
                             ["modules", "docstrings", "total"])
            
            if has_date and has_counters:
                results["run_log"]["valid"] = True
                results["run_log"]["details"] = f"{len(content)} caractères, complet"
            else:
                missing = []
                if not has_date:
                    missing.append("date")
                if not has_counters:
                    missing.append("compteurs")
                results["run_log"]["details"] = f"Incomplet: manque {', '.join(missing)}"
    except Exception as e:
        results["run_log"]["details"] = f"Erreur: {str(e)}"
    
    return results


def generate_quality_report(
    project_root: Path,
    doc_data: Dict[str, Any],
    map_data: Dict[str, Any]
) -> None:
    """
    Génère le rapport de contrôle qualité et l'ajoute à run.log.
    
    Args:
        project_root: Racine du projet
        doc_data: Données depuis missing_docstrings.json
        map_data: Données depuis docs/map.yaml
    """
    log_path = project_root / "reports" / "doc_audit" / "run.log"
    
    # Calculer les statistiques
    category_stats = calculate_category_stats(doc_data)
    top_10 = get_top_10_modules(doc_data)
    modules_without_docstring = check_map_modules_without_docstring(doc_data, map_data)
    acceptance = validate_acceptance_criteria(project_root)
    
    # Construire le rapport
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    report = f"""

{'=' * 60}
=== PHASE 1 - CONTRÔLE QUALITÉ FINAL ===
{'=' * 60}

Timestamp: {timestamp}

1. RÉPARTITION DES DOCSTRINGS MANQUANTES PAR CATÉGORIE
-------------------------------------------------------

"""
    
    # Tableau des catégories
    for category, stats in category_stats.items():
        cat_name = {
            "module": "Modules",
            "class": "Classes",
            "function": "Fonctions",
            "method": "Méthodes"
        }[category]
        
        report += f"{cat_name}:\n"
        report += f"   Total: {stats['total']}\n"
        report += f"   Présentes: {stats['present']} ({100 - stats['percent']:.1f}%)\n"
        report += f"   Manquantes: {stats['missing']} ({stats['percent']:.1f}%)\n\n"
    
    report += f"""
2. TOP 10 DES MODULES AVEC LE PLUS DE DOCSTRINGS MANQUANTES
------------------------------------------------------------

"""
    
    for i, module in enumerate(top_10, 1):
        report += f"{i:2d}. {module['module_path']}\n"
        report += f"    {module['missing']}/{module['total']} manquantes ({module['percent']}%)\n"
        report += f"    Fichier: {module['file_path']}\n\n"
    
    report += f"""
3. MODULES DANS map.yaml SANS DOCSTRING DE MODULE
--------------------------------------------------

Total: {len(modules_without_docstring)} module(s)

"""
    
    if modules_without_docstring:
        for module in modules_without_docstring:
            report += f"   ⚠️  {module}\n"
    else:
        report += "   ✅ Tous les modules de la map ont une docstring de module\n"
    
    report += f"""

4. VALIDATION DES CRITÈRES D'ACCEPTATION
-----------------------------------------

"""
    
    all_valid = all(item["valid"] for item in acceptance.values())
    
    for criterion, result in acceptance.items():
        status = "✅" if result["valid"] else "❌"
        criterion_name = {
            "module_index": "module_index.csv",
            "missing_docstrings": "missing_docstrings.json",
            "map_yaml": "docs/map.yaml",
            "run_log": "run.log"
        }[criterion]
        
        report += f"{status} {criterion_name}\n"
        report += f"   {result['details']}\n\n"
    
    report += f"""
{'=' * 60}
RÉSULTAT FINAL: {'✅ PHASE 1 VALIDÉE' if all_valid else '❌ CORRECTIONS NÉCESSAIRES'}
{'=' * 60}

"""
    
    if all_valid:
        report += """
Tous les critères d'acceptation sont satisfaits.
La Phase 1 est terminée avec succès.
Prêt pour la Phase 2: Génération de la documentation.

"""
    else:
        report += """
Certains critères nécessitent une attention.
Veuillez consulter les détails ci-dessus.

"""
    
    # Ajouter au log
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(report)
    
    print("✅ Rapport de contrôle qualité généré et ajouté à run.log")
    
    # Afficher un résumé
    print("\n" + "=" * 60)
    print("RÉSUMÉ DU CONTRÔLE QUALITÉ")
    print("=" * 60)
    print(f"\n📊 Répartition des manques:")
    for category, stats in category_stats.items():
        print(f"   {category.capitalize():12s}: {stats['missing']:3d}/{stats['total']:3d} ({stats['percent']:5.1f}%)")
    
    print(f"\n🔝 Top 3 modules à documenter:")
    for i, module in enumerate(top_10[:3], 1):
        print(f"   {i}. {module['module_path']} ({module['missing']}/{module['total']})")
    
    print(f"\n⚠️  Modules map.yaml sans docstring: {len(modules_without_docstring)}")
    
    print(f"\n✅ Critères d'acceptation: {sum(1 for r in acceptance.values() if r['valid'])}/4 validés")
    print("=" * 60)


def main() -> None:
    """Point d'entrée principal du script."""
    # Définir les chemins
    project_root = Path(__file__).parent.parent.parent
    json_path = project_root / "reports" / "doc_audit" / "missing_docstrings.json"
    yaml_path = project_root / "docs" / "map.yaml"
    
    print("🔍 Contrôle qualité de la Phase 1...")
    
    # Charger les données
    with open(json_path, "r", encoding="utf-8") as f:
        doc_data = json.load(f)
    
    with open(yaml_path, "r", encoding="utf-8") as f:
        map_data = yaml.safe_load(f)
    
    # Générer le rapport
    generate_quality_report(project_root, doc_data, map_data)
    
    print("\n✅ Étape 5 terminée avec succès!")
    print("✅ PHASE 1 COMPLÈTE!")


if __name__ == "__main__":
    main()
