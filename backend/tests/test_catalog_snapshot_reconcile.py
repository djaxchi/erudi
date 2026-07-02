"""Zero-network catalog reconcile from the bundled snapshot (#131, #163).

The live-HF background resync is gone: at every boot the catalog is reconciled
from the snapshot that ships with the app, with the same in-place semantics as
the old resync (#123) — match by link, stable ids, downloaded (local=1) and
in-progress (local=2) rows never touched. The catalog follows app releases,
needs zero network, and never mutates mid-session. Runs against the real
pgserver test cluster (savepoint rollback per test).
"""
import asyncio

import pytest

from src.core import config
from src.database import catalog_snapshot as snap_mod
from src.database import seed as seed_mod
from src.database.seed import Database_Seeder
from src.entities.Llm import Llm
from src.entities.StartupVariables import StartupVariables

pytestmark = pytest.mark.integration


class _Eng:
    FORMAT_TAG = "gguf"


def _entry(link, name=None, is_base=True, **overrides):
    """Fabricate a snapshot entry the way catalog_snapshot.llm_to_dict writes them."""
    entry = {
        "name": name or link.split("/")[-1],
        "link": link,
        "type": "qwen",
        "quantized": True,
        "model_metadata": None,
        "param_size": 1.0,
        "supports_tools": None,
        "is_base": is_base,
        "category": "general",
    }
    entry.update(overrides)
    return entry


def _llm(**kw):
    kw.setdefault("type", "x")
    kw.setdefault("quantized", False)
    kw.setdefault("param_size", 1.0)
    kw.setdefault("is_base", False)
    return Llm(**kw)


def _use_snapshot(monkeypatch, entries):
    """Serve `entries` through the exact loader the reconcile path uses."""
    monkeypatch.setattr(config, "LLM_Engine", _Eng)
    monkeypatch.setattr(snap_mod, "load_catalog_snapshot", lambda tag: entries)


def _stub_side_steps(monkeypatch):
    """Keep the unrelated startup steps cheap + DB-only (mirrors test_model_catalog)."""

    class _NoCleanup:
        def __init__(self, *a, **k):
            pass

        def cleanup_all_unfinished_jobs(self):
            return {}

    class _NoHw:
        def __init__(self, *a, **k):
            pass

        def initialize_if_needed(self):
            return False

    monkeypatch.setattr(seed_mod, "Job_Cleanup_Service", _NoCleanup)
    monkeypatch.setattr(seed_mod, "Hardware_Initializer", _NoHw)


class TestReconcileCatalogFromSnapshot:
    """reconcile_catalog_from_snapshot applies the bundled snapshot to local=0."""

    def test_empty_catalog_inserts_all_snapshot_entries(self, test_db_session, monkeypatch):
        db = test_db_session
        _use_snapshot(monkeypatch, [
            _entry("org/base-GGUF", is_base=True),
            _entry("org/derived-GGUF", is_base=False),
        ])

        res = Database_Seeder().reconcile_catalog_from_snapshot(db)

        assert res["resynced"] is True
        assert res["base_models_added"] == 2      # 2 inserted
        assert res["derived_models_added"] == 0   # 0 updated
        rows = {r.link: r for r in db.query(Llm).filter(Llm.local == 0).all()}
        assert set(rows) == {"org/base-GGUF", "org/derived-GGUF"}
        assert rows["org/base-GGUF"].is_base is True
        assert rows["org/derived-GGUF"].is_base is False

    def test_changed_entry_updates_in_place_same_pk(self, test_db_session, monkeypatch):
        db = test_db_session
        db.add(_llm(name="Old Name", local=0, link="org/base-GGUF", param_size=1.0))
        db.commit()
        old_id = db.query(Llm).filter(Llm.link == "org/base-GGUF").one().id

        _use_snapshot(monkeypatch, [_entry("org/base-GGUF", name="New Name", param_size=1.5)])
        Database_Seeder().reconcile_catalog_from_snapshot(db)

        row = db.query(Llm).filter(Llm.link == "org/base-GGUF").one()
        assert row.id == old_id                   # in-place update → pk preserved
        assert row.name == "New Name"
        assert row.param_size == 1.5

    def test_local0_row_absent_from_snapshot_is_deleted(self, test_db_session, monkeypatch):
        db = test_db_session
        db.add_all([
            _llm(name="Stays", local=0, link="org/base-GGUF"),
            _llm(name="Vanished", local=0, link="stale/gone-GGUF"),
        ])
        db.commit()

        _use_snapshot(monkeypatch, [_entry("org/base-GGUF")])
        Database_Seeder().reconcile_catalog_from_snapshot(db)

        links = {r.link for r in db.query(Llm).filter(Llm.local == 0).all()}
        assert links == {"org/base-GGUF"}

    def test_downloaded_and_in_progress_rows_never_touched(self, test_db_session, monkeypatch):
        db = test_db_session
        db.add_all([
            _llm(name="Mine", local=1, link="/data/models/9"),
            _llm(name="WIP", local=2, link="repo/wip-GGUF"),
        ])
        db.commit()

        _use_snapshot(monkeypatch, [_entry("org/base-GGUF")])
        Database_Seeder().reconcile_catalog_from_snapshot(db)

        rows = {r.link: r.local for r in db.query(Llm).all()}
        assert rows["/data/models/9"] == 1        # local=1 untouched
        assert rows["repo/wip-GGUF"] == 2         # local=2 untouched
        assert rows["org/base-GGUF"] == 0

    def test_supports_tools_survives_reconcile_update(self, test_db_session, monkeypatch):
        db = test_db_session
        db.add(_llm(name="Base", local=0, link="org/base-GGUF", supports_tools=True))
        db.commit()

        # Snapshot carries supports_tools=None — the post-download detection must
        # not be clobbered (excluded from the reconciled fields).
        _use_snapshot(monkeypatch, [_entry("org/base-GGUF", name="Refreshed")])
        Database_Seeder().reconcile_catalog_from_snapshot(db)

        row = db.query(Llm).filter(Llm.link == "org/base-GGUF").one()
        assert row.supports_tools is True
        assert row.name == "Refreshed"            # but mutable fields did refresh

    def test_no_snapshot_is_a_noop(self, test_db_session, monkeypatch):
        db = test_db_session
        db.add(_llm(name="Keep Me", local=0, link="keep/me-GGUF"))
        db.commit()

        _use_snapshot(monkeypatch, [])
        res = Database_Seeder().reconcile_catalog_from_snapshot(db)

        assert res == {"resynced": False}
        assert db.query(Llm).filter(Llm.link == "keep/me-GGUF").count() == 1

    def test_offline_mode_flag_cleared_on_successful_reconcile(self, test_db_session, monkeypatch):
        """An install whose FIRST boot fell back to the minimal offline JSON
        (offline_mode=True) must stop reporting offline once a boot applies the
        FULL bundled snapshot — the snapshot is not the JSON fallback."""
        db = test_db_session
        db.add(StartupVariables(offline_mode=True))
        db.commit()

        _use_snapshot(monkeypatch, [_entry("org/base-GGUF")])
        res = Database_Seeder().reconcile_catalog_from_snapshot(db)

        assert res["resynced"] is True
        sv = db.query(StartupVariables).first()
        assert sv.offline_mode is False           # cleared with the other stamps

    def test_successful_reconcile_without_startup_vars_row_does_not_crash(
        self, test_db_session, monkeypatch
    ):
        db = test_db_session
        assert db.query(StartupVariables).count() == 0  # no singleton row yet

        _use_snapshot(monkeypatch, [_entry("org/base-GGUF")])
        res = Database_Seeder().reconcile_catalog_from_snapshot(db)

        assert res["resynced"] is True            # stamping is guarded, no crash

    def test_reconcile_makes_zero_network_calls(self, test_db_session, monkeypatch):
        """ZERO NETWORK guarantee: the reconcile path must never construct an HF
        client nor probe connectivity."""
        db = test_db_session

        def _no_network(*a, **k):
            raise AssertionError("HF client must never be constructed on the reconcile path")

        monkeypatch.setattr(seed_mod, "get_hf_api", _no_network)
        monkeypatch.setattr(seed_mod, "is_online", _no_network)
        monkeypatch.setattr(config, "get_hf_api", _no_network)

        _use_snapshot(monkeypatch, [_entry("org/base-GGUF")])
        res = Database_Seeder().reconcile_catalog_from_snapshot(db)
        assert res["resynced"] is True


class TestCategoryReconcileFromSnapshot:
    """#192 (regression of #184): booting against an UNCLASSIFIED snapshot (a
    pre-#122 artifact — no ``category`` key, or an explicit null) must never
    collapse the DB's classified categories to "general". Snapshots that DO
    carry real categories still propagate them, and brand-new unclassified
    entries still land on the default bucket."""

    def test_entry_without_category_key_keeps_existing_category(self, test_db_session, monkeypatch):
        db = test_db_session
        db.add(_llm(name="Coder", local=0, link="org/coder-GGUF", category="code"))
        db.commit()

        entry = _entry("org/coder-GGUF", name="Coder refreshed")
        del entry["category"]                     # shape of the bundled #192 snapshots
        _use_snapshot(monkeypatch, [entry])
        Database_Seeder().reconcile_catalog_from_snapshot(db)

        row = db.query(Llm).filter(Llm.link == "org/coder-GGUF").one()
        assert row.category == "code"             # classification survives the boot
        assert row.name == "Coder refreshed"      # other mutable fields did refresh

    def test_entry_with_null_category_keeps_existing_category(self, test_db_session, monkeypatch):
        db = test_db_session
        db.add(_llm(name="Coder", local=0, link="org/coder-GGUF", category="code"))
        db.commit()

        _use_snapshot(monkeypatch, [_entry("org/coder-GGUF", category=None)])
        Database_Seeder().reconcile_catalog_from_snapshot(db)

        row = db.query(Llm).filter(Llm.link == "org/coder-GGUF").one()
        assert row.category == "code"

    def test_classified_entry_updates_category(self, test_db_session, monkeypatch):
        # A release whose snapshot reclassifies a model must still propagate it.
        db = test_db_session
        db.add(_llm(name="Model", local=0, link="org/model-GGUF", category="general"))
        db.commit()

        _use_snapshot(monkeypatch, [_entry("org/model-GGUF", category="reasoning")])
        Database_Seeder().reconcile_catalog_from_snapshot(db)

        row = db.query(Llm).filter(Llm.link == "org/model-GGUF").one()
        assert row.category == "reasoning"

    def test_new_entry_without_category_inserts_as_general(self, test_db_session, monkeypatch):
        # Coalescing to the default bucket is an INSERT-only behavior.
        db = test_db_session

        entry = _entry("org/new-GGUF")
        del entry["category"]
        _use_snapshot(monkeypatch, [entry])
        Database_Seeder().reconcile_catalog_from_snapshot(db)

        row = db.query(Llm).filter(Llm.link == "org/new-GGUF").one()
        assert row.category == "general"

    def test_first_boot_seed_from_unclassified_snapshot_lands_on_general(
        self, test_db_session, monkeypatch
    ):
        """First boot seeds via a raw add_all of dict_to_llm rows (no reconcile):
        an unclassified entry (category=None) must still satisfy the NOT NULL
        column on the REAL cluster, landing on the "general" default."""
        db = test_db_session

        entry = _entry("org/first-GGUF")
        del entry["category"]
        _use_snapshot(monkeypatch, [entry])

        n = seed_mod.Model_Seeder(db=db, hf_api=None).seed_from_snapshot()

        assert n == 1
        row = db.query(Llm).filter(Llm.link == "org/first-GGUF").one()
        assert row.category == "general"


class TestPopulateStartupData:
    """populate_startup_data reconciles from the snapshot at every boot — no
    background-refresh flag, StartupVariables stamped on success."""

    def test_no_background_refresh_key_and_stamps_last_seeded_at(self, test_db_session, monkeypatch):
        db = test_db_session
        _use_snapshot(monkeypatch, [_entry("org/base-GGUF")])
        _stub_side_steps(monkeypatch)

        res = asyncio.run(Database_Seeder().populate_startup_data(db=db))

        assert "needs_background_refresh" not in res
        assert res["base_models_added"] == 1
        assert res["models_seeded"] is True
        sv = db.query(StartupVariables).first()
        assert sv is not None
        assert sv.models_seeded is True
        assert sv.last_seeded_at is not None      # stamped by the reconcile

    def test_empty_catalog_no_snapshot_falls_back_to_initial_seed(self, test_db_session, monkeypatch):
        db = test_db_session
        _use_snapshot(monkeypatch, [])

        class _CountingSeeder:
            def __init__(self, *a, **k):
                pass

            def seed_initial_catalog(self):
                return 7

        monkeypatch.setattr(seed_mod, "Model_Seeder", _CountingSeeder)
        _stub_side_steps(monkeypatch)

        res = asyncio.run(Database_Seeder().populate_startup_data(db=db))

        assert "needs_background_refresh" not in res
        assert res["base_models_added"] == 7      # minimal offline fallback used
