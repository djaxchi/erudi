"""
PyInstaller spec for CPU-only Erudi backend (variant: cpu).

This spec is based on `backend/backend.spec` but sets the build variant to
`cpu` and tightens excludes useful for CPU-only packaging.
"""
import os
from pathlib import Path

project_root = Path(__file__).resolve().parent

# Force variant for template logic
os.environ['ERUDI_BUILD_VARIANT'] = 'cpu'

# Minimal additional CPU-specific adjustments
EXTRA_EXCLUDES = ['cuda', 'cupy', 'cudf', 'mlx_vlm']

# Reuse the main template by importing it (it defines Analysis/EXE/COLLECT when
# PyInstaller is available). The template reads ERUDI_BUILD_VARIANT and will
# adapt excludes/binaries accordingly.
try:
    # Importing as module: execute backend/backend.spec as Python code
    import importlib.util
    spec_path = project_root.joinpath('backend.spec')
    spec_name = 'erudi_backend_spec_template'
    spec = importlib.util.spec_from_file_location(spec_name, str(spec_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # If the template exposes `excludes`, extend it here
    if hasattr(module, 'excludes'):
        module.excludes.extend(EXTRA_EXCLUDES)

except Exception:
    # When running without PyInstaller or on static analysis, the import may fail.
    # Provide a fallback minimal spec for static editors.
    pass
