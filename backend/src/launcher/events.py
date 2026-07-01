"""Shared newline-delimited JSON lifecycle-event emitter.

Both the cross-platform launcher (``backend/run.py``) and the FastAPI
``lifespan`` run in the same process and share stdout. The Electron main
process (``frontend/src/main.js``) parses each stdout line as JSON and
tolerates interleaved non-JSON log lines. Keeping a single emitter here means
the launcher and the app agree on the wire format, and startup *progress*
(phase) events can originate from inside the lifespan.

Event shapes:
    - {"event": "starting", ...}                     (run.py)
    - {"event": "phase", "phase": "<name>"}          (lifespan, via emit_phase)
    - {"event": "ready", "port": N}                  (run.py)
    - {"event": "shutdown"}                           (run.py)
    - {"event": "startup_error", "code": "...", ...}  (run.py)
"""

from __future__ import annotations

import json


def emit_event(payload: dict) -> None:
    """Print a structured JSON lifecycle event (newline-delimited) to stdout."""
    print(json.dumps(payload), flush=True)


def emit_phase(phase: str) -> None:
    """Emit a startup-progress phase the frontend can surface on the loader.

    Phases are informational only — the frontend still gates readiness on the
    ``ready`` event / a confirming health check, never on a phase.
    """
    emit_event({"event": "phase", "phase": phase})
