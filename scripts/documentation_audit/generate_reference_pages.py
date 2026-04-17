#!/usr/bin/env python3
"""Generate MkDocs reference pages from map.yaml.

Minimal script that creates one .md file per domain with mkdocstrings directives.
Logs only errors (missing modules) and summary.
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml")
    sys.exit(1)


def generate_reference_pages(map_path: Path, out_dir: Path) -> dict:
    """Generate reference markdown files from map.yaml.
    
    Args:
        map_path: Path to docs/map.yaml
        out_dir: Output directory (docs/reference/)
    
    Returns:
        dict with 'created', 'modules_not_found' keys
    """
    # Load map
    with open(map_path) as f:
        map_data = yaml.safe_load(f)
    
    reference = map_data.get('reference', {})
    
    created_files = []
    modules_not_found = []
    
    # Ensure output directory exists
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate one .md per domain
    for domain_key, modules in reference.items():
        # Capitalize domain name for title
        title = domain_key.replace('_', ' ').title()
        
        # Create markdown content
        lines = [f"# {title}\n"]
        
        seen_modules = set()
        for module_path in modules:
            if module_path in seen_modules:
                continue
            seen_modules.add(module_path)
            
            # Use module path as-is (src.* format works with mkdocstrings)
            import_path = module_path
            
            # Add mkdocstrings directive (no import check - let mkdocstrings handle it)
            lines.append(f"::: {import_path}\n")
        
        # Write file
        output_file = out_dir / f"{domain_key}.md"
        with open(output_file, 'w') as f:
            f.write('\n'.join(lines))
        
        created_files.append(output_file.name)
    
    return {
        'created': created_files,
        'modules_not_found': modules_not_found
    }


def main():
    parser = argparse.ArgumentParser(description='Generate MkDocs reference pages')
    parser.add_argument('--map', type=Path, required=True, help='Path to map.yaml')
    parser.add_argument('--out', type=Path, required=True, help='Output directory')
    args = parser.parse_args()
    
    print(f"Generating reference pages from {args.map}...")
    
    result = generate_reference_pages(args.map, args.out)
    
    print(f"✓ Created {len(result['created'])} reference pages:")
    for filename in result['created']:
        print(f"  - {filename}")
    
    if result['modules_not_found']:
        print(f"\n⚠ {len(result['modules_not_found'])} modules not found:")
        for msg in result['modules_not_found']:
            print(f"  - {msg}")
    
    print(f"\nDone. Pages written to {args.out}/")


if __name__ == '__main__':
    main()
