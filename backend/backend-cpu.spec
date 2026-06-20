"""
PyInstaller spec for the CPU/Windows Erudi backend (variant: cpu).

Thin wrapper over `backend/backend.spec`: it sets the CPU build variant, then
executes the shared template **in this spec's own namespace** so the template
sees the PyInstaller-injected globals (SPECPATH, DISTPATH, …).

Note: PyInstaller runs a .spec via exec() WITHOUT defining `__file__`, and a
nested importlib load would give the template a fresh namespace missing those
globals — both of which broke the previous wrapper. Use `SPECPATH` (the spec's
directory, injected by PyInstaller) and a plain in-namespace exec instead.
"""
import os
from pathlib import Path

# Mark the build variant (available to the template / runtime hooks if needed).
os.environ["ERUDI_BUILD_VARIANT"] = "cpu"

# SPECPATH is injected by PyInstaller and points at this spec's directory
# (= backend/). Execute the shared template here so it inherits SPECPATH & co.
_template = Path(SPECPATH) / "backend.spec"
exec(compile(_template.read_text(), str(_template), "exec"))
