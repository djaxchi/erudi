"""Catalog ↔ engine invariants (#95), post auto-catalog refactor.

The catalog is built ONLY from repos carrying the engine's format tag (filter="mlx"
/ filter="gguf"), and base ids are resolved to their public quant by the resolver
(see test_model_resolver). So there is no hand-maintained MODEL_MAPPING and no
name-based allowlist: everything in the catalog is runnable by construction, and
the lone exclusion is KNOWN_BROKEN (quants that load-crash). These are pure
class-attribute / schema checks — no network, CI-safe.
"""

import pytest

from src.core import config
from src.core.exceptions import UnsupportedPlatformException
from src.database.seed import Database_Seeder
from src.domains.llms import services
from src.utils.hf_model_metadata import humanize_model_name
from src.engines.base_llama_cpp_engine import BaseLlamaCppEngine
from src.engines.cpu_engine import CPU_Engine
from src.engines.cuda_engine import CUDA_Engine
from src.engines.mlx_engine import MLX_Engine

# Representative base ids (the live catalog is org-discovered, not a static list).
CATALOG_LINKS = [
    "google/gemma-3-270m-it", "google/gemma-2-2b-it", "google/gemma-3-4b-it",
    "google/gemma-3-12b-it", "google/gemma-4-E2B-it", "google/gemma-4-26b-a4b-it",
    "google/gemma-4-31b-it",
]


class TestEngineFormatTag:
    """Each engine declares its HF format tag; the community/base search filters on
    it (across all of HF, any author) instead of a hand-maintained mapping/org."""

    def test_format_tag_per_engine(self):
        assert MLX_Engine.FORMAT_TAG == "mlx"
        assert BaseLlamaCppEngine.FORMAT_TAG == "gguf"
        assert CPU_Engine.FORMAT_TAG == "gguf"
        assert CUDA_Engine.FORMAT_TAG == "gguf"

    def test_uses_gguf_is_inherited_true(self):
        assert BaseLlamaCppEngine.USES_GGUF is True
        assert CPU_Engine.USES_GGUF is True
        assert CUDA_Engine.USES_GGUF is True

    def test_community_search_filters_on_format_tag(self):
        kw = MLX_Engine.community_search_kwargs("gemma 1b")
        assert kw["filter"] == "mlx" and kw["search"] == "gemma 1b"
        for engine in (CPU_Engine, CUDA_Engine):
            kw = engine.community_search_kwargs("gemma 1b")
            assert kw["filter"] == "gguf" and kw["search"] == "gemma 1b"


class TestOrgDiscovery:
    """discover_instruct_models is permissive but drops quant/adapter/non-final
    noise, applies a downloads floor, dedups by normalized slug, and caps the count."""

    def _seeder(self, ids):
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from src.database.seed import Model_Seeder
        api = MagicMock()
        api.list_models.return_value = [SimpleNamespace(id=i, downloads=d) for i, d in ids]
        return Model_Seeder(db=None, hf_api=api)

    def test_filters_quants_and_floor(self):
        seeder = self._seeder([
            ("Qwen/Qwen3-8B", 100000),                  # keep
            ("Qwen/Qwen3-8B-GGUF", 50000),              # skip: quant
            ("Qwen/Qwen3-4B", 30000),                   # keep
            ("Qwen/Qwen2.5-7B-Instruct-AWQ", 9000),     # skip: quant
            ("Qwen/tiny-thing", 10),                    # skip: below floor
        ])
        links = [c.link for c in seeder.discover_instruct_models("Qwen", "qwen", min_downloads=1000)]
        assert "Qwen/Qwen3-8B" in links and "Qwen/Qwen3-4B" in links
        assert all(x not in " ".join(links) for x in ("GGUF", "AWQ"))
        assert "Qwen/tiny-thing" not in links

    def test_dedups_by_normalized_slug(self):
        seeder = self._seeder([
            ("Qwen/Qwen3-8B", 100000),
            ("Qwen/Qwen3-8B-bf16", 90000),  # same normalized slug → dropped
        ])
        configs = seeder.discover_instruct_models("Qwen", "qwen", min_downloads=1)
        assert len(configs) == 1

    def test_caps_top_n(self):
        seeder = self._seeder([(f"Org/Model-{i}-Instruct", 100000 - i) for i in range(20)])
        assert len(seeder.discover_instruct_models("Org", "x", top_n=5, min_downloads=1)) == 5

    def test_search_failure_returns_empty(self):
        from unittest.mock import MagicMock
        from src.database.seed import Model_Seeder
        api = MagicMock()
        api.list_models.side_effect = RuntimeError("boom")
        assert Model_Seeder(db=None, hf_api=api).discover_instruct_models("Org", "x") == []


class TestRunnabilityPredicate:
    """is_runnable is now KNOWN_BROKEN-only: catalog entries are engine-format by
    construction (they came from a filter=FORMAT_TAG search), so the only thing to
    exclude is a quant that downloads but crashes at load."""

    def test_format_quants_are_runnable(self):
        assert MLX_Engine.is_runnable("mlx-community/gemma-3-1b-it-4bit") is True
        assert MLX_Engine.is_runnable("lmstudio-community/Hermes-4-70B-MLX-4bit") is True  # non-org
        assert CPU_Engine.is_runnable("unsloth/gemma-3-1b-it-GGUF") is True
        assert CUDA_Engine.is_runnable("mradermacher/Some-Cool-Distill-GGUF") is True  # community

    def test_known_broken_is_not_runnable(self):
        assert MLX_Engine.is_runnable("mlx-community/gemma-4-e2b-it-4bit") is False
        assert "mlx-community/gemma-4-e2b-it-4bit" in MLX_Engine.KNOWN_BROKEN
        # llama.cpp has no known-broken quants → everything format-tagged runs
        assert CPU_Engine.KNOWN_BROKEN == frozenset()


class TestHumanizedNames:
    """Display names are derived from the real slug — exact, unambiguous."""

    @pytest.mark.parametrize("link,expected", [
        ("google/gemma-3-270m-it",                "Gemma 3 270M Instruct"),
        ("google/gemma-2-2b-it",                  "Gemma 2 2B Instruct"),
        ("google/gemma-3-4b-it",                  "Gemma 3 4B Instruct"),
        ("google/gemma-3-12b-it",                 "Gemma 3 12B Instruct"),
        ("google/gemma-4-E2B-it",                 "Gemma 4 E2B Instruct"),
        ("google/gemma-4-26b-a4b-it",             "Gemma 4 26B A4B Instruct"),
        ("google/gemma-4-31b-it",                 "Gemma 4 31B Instruct"),
        ("mistralai/Mistral-7B-Instruct-v0.3",    "Mistral 7B Instruct v0.3"),
        ("mistralai/Ministral-8B-Instruct-2410",  "Ministral 8B Instruct 2410"),
        ("mistralai/Mistral-Nemo-Instruct-2407",  "Mistral Nemo Instruct 2407"),
        ("meta-llama/Llama-3.1-8B-Instruct",      "Llama 3.1 8B Instruct"),
        ("Qwen/Qwen2.5-7B-Instruct",              "Qwen2.5 7B Instruct"),
    ])
    def test_humanize(self, link, expected):
        assert humanize_model_name(link) == expected

    def test_no_catalog_name_is_ambiguous_gemma(self):
        for link in CATALOG_LINKS:
            name = humanize_model_name(link)
            if name.startswith("Gemma"):
                assert name.split()[1].replace(".", "").isdigit(), f"ambiguous: {name}"


class TestRunnableExposedInResponse:
    """LLMResponse surfaces a computed `runnable` so the UI can disable/tag models."""

    def test_remote_quant_is_runnable(self, monkeypatch):
        from src.domains.llms.schemas import LLMResponse
        monkeypatch.setattr(config, "LLM_Engine", CPU_Engine)
        r = LLMResponse(id=1, name="X", local=0, link="unsloth/gemma-3-1b-it-GGUF")
        assert r.runnable is True
        assert r.model_dump()["runnable"] is True

    def test_remote_known_broken_is_not_runnable(self, monkeypatch):
        from src.domains.llms.schemas import LLMResponse
        monkeypatch.setattr(config, "LLM_Engine", MLX_Engine)
        r = LLMResponse(id=2, name="Y", local=0, link="mlx-community/gemma-4-e2b-it-4bit")
        assert r.runnable is False

    def test_downloaded_model_always_runnable(self, monkeypatch):
        from src.domains.llms.schemas import LLMResponse
        monkeypatch.setattr(config, "LLM_Engine", MLX_Engine)
        # local=1 (downloaded) → runnable even if its link were KNOWN_BROKEN
        r = LLMResponse(id=3, name="Z", local=1, link="/data/models/3")
        assert r.runnable is True


class TestRemoteCatalogResync:
    """resync_remote_catalog reconciles local=0 with HF atomically: it preserves
    downloaded (local=1) and in-progress (local=2) models, and never empties the
    catalog if the fetch comes back empty (network failure)."""

    def _llm(self, **kw):
        from src.entities.Llm import Llm
        kw.setdefault("type", "x")
        kw.setdefault("quantized", False)
        kw.setdefault("param_size", 1.0)
        return Llm(**kw)

    def test_swap_replaces_remote_keeps_downloaded(self, test_db_session):
        from unittest.mock import MagicMock
        from src.entities.Llm import Llm

        db = test_db_session
        db.add_all([
            self._llm(name="Old Stale", local=0, link="stale/gone-GGUF"),
            self._llm(name="My Model", local=1, link="/data/models/9"),
            self._llm(name="Downloading", local=2, link="repo/wip-GGUF"),
        ])
        db.commit()

        fresh = self._llm(name="Gemma 3 1B Instruct", local=0, link="unsloth/gemma-3-1b-it-GGUF", type="gemma")
        ms = MagicMock()
        ms.build_base_models.return_value = [fresh]
        ms.build_derived_models.return_value = []

        res = Database_Seeder().resync_remote_catalog(db, ms)

        assert res["resynced"] is True
        rows = {r.link: r.local for r in db.query(Llm).all()}
        assert "stale/gone-GGUF" not in rows
        assert rows["unsloth/gemma-3-1b-it-GGUF"] == 0
        assert rows["/data/models/9"] == 1
        assert rows["repo/wip-GGUF"] == 2

    def test_derived_requant_of_base_is_deduped(self, test_db_session):
        from unittest.mock import MagicMock
        from src.entities.Llm import Llm

        db = test_db_session
        base = self._llm(name="Gemma 3 1B Instruct", local=0, link="unsloth/gemma-3-1b-it-GGUF", type="gemma")
        # another quant of the SAME base (normalizes to gemma-3-1b-it) → must drop
        requant = self._llm(name="dup", local=0, link="bartowski/google_gemma-3-1b-it-GGUF", type="gemma")
        # a genuine finetune (different slug) → must stay
        finetune = self._llm(name="Dolphin", local=0, link="cognitivecomputations/dolphin-gemma-3-1b-GGUF", type="gemma")
        ms = MagicMock()
        ms.build_base_models.return_value = [base]
        ms.build_derived_models.return_value = [requant, finetune]

        Database_Seeder().resync_remote_catalog(db, ms)
        links = {r.link for r in db.query(Llm).filter(Llm.local == 0).all()}
        assert "unsloth/gemma-3-1b-it-GGUF" in links          # base kept
        assert "bartowski/google_gemma-3-1b-it-GGUF" not in links  # re-quant of base dropped
        assert "cognitivecomputations/dolphin-gemma-3-1b-GGUF" in links  # finetune kept

    def test_empty_fetch_does_not_wipe_catalog(self, test_db_session):
        from unittest.mock import MagicMock
        from src.entities.Llm import Llm

        db = test_db_session
        db.add(self._llm(name="Keep Me", local=0, link="keep/me-GGUF"))
        db.commit()

        ms = MagicMock()
        ms.build_base_models.return_value = []
        ms.build_derived_models.return_value = []

        res = Database_Seeder().resync_remote_catalog(db, ms)
        assert res["resynced"] is False
        assert db.query(Llm).filter(Llm.link == "keep/me-GGUF").count() == 1


class TestNonBlockingCatalogRefresh:
    """refresh_remote_catalog runs the slow HF resync in the BACKGROUND (#109): it
    never blocks boot, stamps last_seeded_at on success, and swallows errors."""

    def _run(self):
        import asyncio
        return asyncio.run(Database_Seeder().refresh_remote_catalog())

    def test_skips_when_offline(self, monkeypatch):
        from unittest.mock import MagicMock
        from src.database import seed as seed_mod
        fake_db = MagicMock()
        monkeypatch.setattr(seed_mod, "is_online", lambda: False)
        monkeypatch.setattr(seed_mod, "SessionLocal", lambda: fake_db)
        assert self._run() == {"resynced": False}
        fake_db.close.assert_called_once()

    def test_resyncs_and_stamps_when_online(self, monkeypatch):
        from unittest.mock import MagicMock
        from src.database import seed as seed_mod
        fake_db = MagicMock()
        sv = MagicMock()
        fake_db.query.return_value.first.return_value = sv
        monkeypatch.setattr(seed_mod, "is_online", lambda: True)
        monkeypatch.setattr(seed_mod, "get_hf_api", lambda: object())
        monkeypatch.setattr(seed_mod, "SessionLocal", lambda: fake_db)
        monkeypatch.setattr(seed_mod, "Model_Seeder", lambda *a, **k: MagicMock())
        monkeypatch.setattr(Database_Seeder, "resync_remote_catalog",
                            lambda self, d, ms: {"resynced": True, "base_models_added": 5, "derived_models_added": 9})
        res = self._run()
        assert res["resynced"] is True
        assert sv.models_seeded is True       # stamped on success
        fake_db.commit.assert_called()
        fake_db.close.assert_called_once()

    def test_swallows_errors(self, monkeypatch):
        from unittest.mock import MagicMock
        from src.database import seed as seed_mod

        def _boom(self, d, ms):
            raise RuntimeError("boom")
        fake_db = MagicMock()
        monkeypatch.setattr(seed_mod, "is_online", lambda: True)
        monkeypatch.setattr(seed_mod, "get_hf_api", lambda: object())
        monkeypatch.setattr(seed_mod, "SessionLocal", lambda: fake_db)
        monkeypatch.setattr(seed_mod, "Model_Seeder", lambda *a, **k: MagicMock())
        monkeypatch.setattr(Database_Seeder, "resync_remote_catalog", _boom)
        res = self._run()
        assert res["resynced"] is False and "error" in res
        fake_db.close.assert_called_once()


class TestDownloadRunnabilityGuard:
    """download_llm rejects a KNOWN_BROKEN target up front (clear error, no crash)."""

    def test_rejects_known_broken(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_Engine", MLX_Engine)
        with pytest.raises(UnsupportedPlatformException):
            services._assert_runnable("mlx-community/gemma-4-e2b-it-4bit")

    def test_allows_normal_quant(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_Engine", MLX_Engine)
        services._assert_runnable("mlx-community/gemma-3-1b-it-4bit")  # no raise
