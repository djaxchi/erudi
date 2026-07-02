"""Boot must not pay for the agent LangChain stack (issue #160, partial scope).

``import src.main`` (what uvicorn does before serving anything) must not pull
the agent-layer LangChain packages — ``langchain`` (create_agent, middleware,
tools) and ``langchain_openai`` (ChatOpenAI) — into ``sys.modules``. Nothing
needs them before the FIRST conversation/arena turn, so their imports are
deferred to function scope in ``src.agents.{runner,model_factory,kb_mode}``.

Deliberately OUT of this guard (still boot-loaded, out of #160-partial scope):
  - ``langchain_core`` / ``langchain_text_splitters`` — pulled at module level
    by ``src.ingestion`` (embeddings/chunking) via the seed path, along with
    sentence_transformers/torch (the dominant boot cost, ~4.3 s measured).
  - ``langchain_postgres`` — pulled by ``src.ingestion.vector_store``.
  - ``langgraph`` — the checkpointer is opened IN the lifespan, so deferring
    its import gains nothing at boot.

The check runs in a subprocess so this test is immune to whatever the pytest
session itself has already imported.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_BACKEND = Path(__file__).resolve().parents[1]
_MARKER = "LOADED_MODULES_JSON:"

_PROBE = f"""
import json, sys
import src.main  # noqa: F401  (what uvicorn imports before serving)
print({_MARKER!r} + json.dumps(sorted(sys.modules)))
"""


def test_import_src_main_does_not_load_agent_langchain_stack():
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE],
        capture_output=True,
        text=True,
        cwd=_BACKEND,
        timeout=180,
    )
    assert proc.returncode == 0, f"import src.main failed:\n{proc.stderr}"
    payload = [ln for ln in proc.stdout.splitlines() if ln.startswith(_MARKER)]
    assert payload, f"probe marker line missing in stdout:\n{proc.stdout}"
    modules = json.loads(payload[-1][len(_MARKER):])

    offenders = [
        m
        for m in modules
        if m == "langchain"
        or m.startswith("langchain.")
        or m == "langchain_openai"
        or m.startswith("langchain_openai.")
    ]
    assert offenders == [], (
        "boot (import src.main) must not load the agent LangChain stack; "
        f"loaded: {offenders}"
    )
