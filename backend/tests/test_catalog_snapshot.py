"""Build-time catalog snapshot (#112): serialize/load round-trip + first-boot
loading. The snapshot is the instant, zero-HF first-boot catalog; offline JSON is
the fallback. Offline unit tests — no network, no real DB."""
import json
from unittest.mock import MagicMock

from src.core import config
from src.database import catalog_snapshot as snap
from src.database.seed import Model_Seeder
from src.entities.Llm import Llm


def test_llm_dict_roundtrip():
    llm = Llm(local=0, name="Qwen3 8B", link="lmstudio/Qwen3-8B-MLX-4bit", type="qwen",
              quantized=True, model_metadata="meta", param_size=8.0, supports_tools=None,
              is_base=True)
    d = snap.llm_to_dict(llm)
    assert d == {
        "name": "Qwen3 8B", "link": "lmstudio/Qwen3-8B-MLX-4bit", "type": "qwen",
        "quantized": True, "model_metadata": "meta", "param_size": 8.0, "supports_tools": None,
        "is_base": True,
    }
    back = snap.dict_to_llm(d)
    assert (back.local, back.name, back.link, back.type, back.param_size) == (
        0, "Qwen3 8B", "lmstudio/Qwen3-8B-MLX-4bit", "qwen", 8.0)
    assert back.is_base is True


def test_dict_to_llm_defaults_is_base_false_when_missing():
    # Old snapshots predate the flag; loading one must not crash and defaults to derived.
    back = snap.dict_to_llm({"name": "X", "link": "y/z", "type": "qwen"})
    assert back.is_base is False


def test_load_missing_snapshot_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(snap.config, "ROOT_DIR", tmp_path)
    assert snap.load_catalog_snapshot("mlx") == []


def test_load_existing_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(snap.config, "ROOT_DIR", tmp_path)
    db_dir = tmp_path / "src" / "database"
    db_dir.mkdir(parents=True)
    (db_dir / "catalog_snapshot_gguf.json").write_text(json.dumps([{"name": "x", "link": "y/z"}]))
    assert snap.load_catalog_snapshot("gguf") == [{"name": "x", "link": "y/z"}]


def test_seed_from_snapshot_inserts_local0_rows(monkeypatch):
    class _Eng:
        FORMAT_TAG = "mlx"
    monkeypatch.setattr(config, "LLM_Engine", _Eng)
    monkeypatch.setattr(snap, "load_catalog_snapshot",
                        lambda tag: [{"name": "A", "link": "a/A", "type": "qwen"},
                                     {"name": "B", "link": "b/B", "type": "llama"}])
    db = MagicMock()
    n = Model_Seeder(db=db, hf_api=None).seed_from_snapshot()
    assert n == 2
    rows = db.add_all.call_args[0][0]
    assert [r.name for r in rows] == ["A", "B"]
    assert all(r.local == 0 for r in rows)


def test_seed_from_snapshot_no_tag_returns_zero(monkeypatch):
    class _Eng:
        FORMAT_TAG = None
    monkeypatch.setattr(config, "LLM_Engine", _Eng)
    assert Model_Seeder(db=MagicMock(), hf_api=None).seed_from_snapshot() == 0


def test_seed_initial_catalog_prefers_snapshot(monkeypatch):
    seeder = Model_Seeder(db=MagicMock(), hf_api=None)
    monkeypatch.setattr(seeder, "seed_from_snapshot", lambda: 42)
    tried_offline = {"v": False}

    def _offline():
        tried_offline["v"] = True
        return 7
    monkeypatch.setattr(seeder, "seed_base_models_offline", _offline)
    assert seeder.seed_initial_catalog() == 42
    assert tried_offline["v"] is False           # snapshot won → offline never tried


def test_seed_initial_catalog_falls_back_to_offline(monkeypatch):
    seeder = Model_Seeder(db=MagicMock(), hf_api=None)
    monkeypatch.setattr(seeder, "seed_from_snapshot", lambda: 0)
    monkeypatch.setattr(seeder, "seed_base_models_offline", lambda: 7)
    assert seeder.seed_initial_catalog() == 7


def test_seed_initial_catalog_never_raises_when_both_fail(monkeypatch):
    # Boot must not crash if neither a snapshot nor the fallback JSON is available.
    def _boom():
        raise RuntimeError("missing")
    seeder = Model_Seeder(db=MagicMock(), hf_api=None)
    monkeypatch.setattr(seeder, "seed_from_snapshot", _boom)
    monkeypatch.setattr(seeder, "seed_base_models_offline", _boom)
    assert seeder.seed_initial_catalog() == 0
