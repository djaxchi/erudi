"""Build-time catalog snapshot (#112): serialize/load round-trip + first-boot
loading. The snapshot is the instant, zero-HF first-boot catalog; offline JSON is
the fallback. Offline unit tests — no network, no real DB."""
import json
import types
from unittest.mock import MagicMock

from src.core import config
from src.database import catalog_snapshot as snap
from src.database import seed as seed_mod
from src.database.seed import Model_Seeder
from src.entities.Llm import Llm


def test_llm_dict_roundtrip():
    llm = Llm(local=0, name="Qwen3 8B", link="lmstudio/Qwen3-8B-MLX-4bit", type="qwen",
              quantized=True, model_metadata="meta", param_size=8.0, supports_tools=None,
              is_base=True, category="general")
    d = snap.llm_to_dict(llm)
    assert d == {
        "name": "Qwen3 8B", "link": "lmstudio/Qwen3-8B-MLX-4bit", "type": "qwen",
        "quantized": True, "model_metadata": "meta", "param_size": 8.0, "supports_tools": None,
        "is_base": True, "category": "general",
    }
    back = snap.dict_to_llm(d)
    assert (back.local, back.name, back.link, back.type, back.param_size) == (
        0, "Qwen3 8B", "lmstudio/Qwen3-8B-MLX-4bit", "qwen", 8.0)
    assert back.is_base is True
    assert back.category == "general"


def test_dict_to_llm_defaults_is_base_false_when_missing():
    # Old snapshots predate the flag; loading one must not crash and defaults to derived.
    back = snap.dict_to_llm({"name": "X", "link": "y/z", "type": "qwen"})
    assert back.is_base is False


def test_dict_to_llm_keeps_unclassified_category_none():
    """#192: pre-#122 snapshots carry no category (or an explicit null). The loader
    must NOT coalesce to "general" — None is the "unclassified" sentinel that lets
    the boot reconcile keep the existing row's classification. Plain inserts still
    land on the Llm column default ("general")."""
    assert snap.dict_to_llm({"name": "X", "link": "y/z", "type": "qwen"}).category is None
    assert snap.dict_to_llm(
        {"name": "X", "link": "y/z", "type": "qwen", "category": None}
    ).category is None


def test_build_path_emits_classified_snapshot_entries(monkeypatch):
    """#192 root cause pin: the bundled snapshots were generated BEFORE #122 wired
    the classifier, so no entry carried a category and every boot reconciled the
    catalog down to "general". The generation path (discovery → creators →
    llm_to_dict, the exact chain generate_snapshot dumps) must consult the
    classifier and emit a real category on every entry."""
    calls = {"n": 0}
    real_categorize = seed_mod.categorize

    def spy(*a, **k):
        calls["n"] += 1
        return real_categorize(*a, **k)

    monkeypatch.setattr(seed_mod, "categorize", spy)

    class _Size:
        def to_string(self):
            return "1 GB"

    monkeypatch.setattr(seed_mod, "format_model_info_metadata", lambda *a, **k: "meta")
    monkeypatch.setattr(seed_mod, "get_model_size_estimate", lambda *a, **k: _Size())
    monkeypatch.setattr(seed_mod, "get_disk_size_after_quant", lambda *a, **k: _Size())

    api = MagicMock()
    api.list_models.side_effect = lambda **kw: (
        [types.SimpleNamespace(id="Qwen/Qwen3-Coder-8B", downloads=100000)]
        if kw.get("pipeline_tag") == "text-generation" else []
    )
    api.model_info.return_value = object()
    seeder = Model_Seeder(db=None, hf_api=api)

    # Base path: discovery classifies; _create_base_llm carries it onto the row.
    (cfg,) = seeder.discover_instruct_models("Qwen", "qwen", min_downloads=1)
    base_entry = snap.llm_to_dict(seeder._create_base_llm(cfg, "quanter/Qwen3-Coder-8B-GGUF"))
    assert base_entry["category"] == "code"

    # Derived path: _create_derived_llm classifies from the community slug/tags.
    model_info = types.SimpleNamespace(modelId="community/foo-r1-GGUF", tags=[],
                                       pipeline_tag="text-generation")
    search_config = types.SimpleNamespace(model_type="x", default_param_size=7.0)
    derived_entry = snap.llm_to_dict(seeder._create_derived_llm(model_info, search_config))
    assert derived_entry["category"] == "reasoning"

    assert calls["n"] >= 2                        # the classifier was actually consulted


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
