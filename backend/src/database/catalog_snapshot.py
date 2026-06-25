"""Build-time catalog snapshot (#112).

The remote catalog — which engine-format quant exists for each foundation model —
is identical for every user on a given engine, yet the runtime resync re-derives it
by hammering the anonymous HF API on each boot (hundreds of calls, minutes). Instead
we resolve it ONCE at build/release time and ship it as JSON per engine format; first
boot loads it instantly with zero HF calls, and the runtime resync becomes an optional
background refresh.

  generate_snapshot()         build (via Database_Seeder.build_fresh_catalog) + dump JSON
  load_catalog_snapshot(tag)  read the shipped JSON (first boot)
  dict_to_llm(entry)          rebuild a detached local=0 Llm row from a snapshot entry

CLI (run at build time, once per engine format):
  python -m src.database.catalog_snapshot              # active engine (mlx on mac)
  ERUDI_FORCE_CPU=1 python -m src.database.catalog_snapshot   # gguf
"""
import json
from pathlib import Path
from typing import Any, Dict, List

from src.core import config
from src.core.logging import logger
from src.entities.Llm import Llm

# Fields persisted per entry. ``local`` is always 0 (a remote suggestion).
_SNAPSHOT_FIELDS = (
    "name", "link", "type", "quantized", "model_metadata", "param_size", "supports_tools",
    "is_base",
)


def snapshot_path(format_tag: str) -> Path:
    """Bundled path the loader resolves at runtime (ROOT_DIR/src/database/...)."""
    return config.ROOT_DIR / "src" / "database" / f"catalog_snapshot_{format_tag}.json"


def llm_to_dict(llm: Llm) -> Dict[str, Any]:
    return {field: getattr(llm, field, None) for field in _SNAPSHOT_FIELDS}


def dict_to_llm(entry: Dict[str, Any]) -> Llm:
    return Llm(
        local=0,
        name=entry["name"],
        link=entry["link"],
        type=entry.get("type"),
        quantized=entry.get("quantized", True),
        model_metadata=entry.get("model_metadata"),
        # Llm validates param_size > 0; snapshots always carry it, but stay defensive.
        param_size=entry.get("param_size") or 7.0,
        supports_tools=entry.get("supports_tools"),
        # Pre-#86 snapshots predate the flag → default to derived/community.
        is_base=entry.get("is_base", False),
    )


def load_catalog_snapshot(format_tag: str) -> List[Dict[str, Any]]:
    """Read the shipped snapshot for an engine format. Returns [] if absent/broken
    (boot must never fail because the snapshot is missing)."""
    path = snapshot_path(format_tag)
    if not path.exists():
        logger.info(f"No catalog snapshot at {path}")
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Loaded {len(data)} catalog entries from snapshot {path.name}")
        return data
    except Exception as e:
        logger.warning(f"Failed to read catalog snapshot {path}: {e}")
        return []


def generate_snapshot() -> Path:
    """Resolve the full remote catalog for the ACTIVE engine and write its snapshot
    JSON. The engine's FORMAT_TAG drives both the resolution and the filename, so run
    this once per engine (mlx natively on mac, gguf via ERUDI_FORCE_CPU=1)."""
    from src.database.seed import Database_Seeder, Model_Seeder

    tag = getattr(config.LLM_Engine, "FORMAT_TAG", None)
    if not tag:
        raise RuntimeError("No engine FORMAT_TAG available — select an engine first")

    seeder = Database_Seeder()
    model_seeder = Model_Seeder(db=None, hf_api=config.get_hf_api(), offline_mode=False)
    base, derived = seeder.build_fresh_catalog(model_seeder)
    entries = [llm_to_dict(m) for m in (base + derived)]

    path = snapshot_path(tag)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=1)
    logger.info(f"Wrote {len(entries)} catalog entries ({len(base)} base + {len(derived)} derived) to {path}")
    return path


def main() -> None:
    if getattr(config, "LLM_Engine", None) is None:
        from src.engines.base_engine import BaseEngine
        config.LLM_Engine = BaseEngine.get_engine()
    path = generate_snapshot()
    print(f"snapshot: {path}")


if __name__ == "__main__":
    main()
