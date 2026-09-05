"""Persisting the verified tool-call wire capability (#298).

- ``unit``: the ``detect_wire_tools`` wrapper (engine verdict, graceful None —
  it must never block download finalization) and the ``LLMResponse`` field.
- ``integration``: the ``llms.supports_tools_wire`` column exists (migration
  ran), a row round-trips, ``LLMResponse`` surfaces it from the ORM, and the
  startup backfill computes+persists it for local rows where it is NULL.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect as sa_inspect

from src.database.seed import Database_Seeder
from src.domains.llms.repository import detect_wire_tools
from src.domains.llms.schemas import LLMResponse
from src.entities.Llm import Llm


# ---------------- unit: detect_wire_tools wrapper ----------------


class _WireEngine:
    @staticmethod
    def compute_wire_tools(local_path):
        return True


class _NoWireEngine:
    @staticmethod
    def compute_wire_tools(local_path):
        return False


class _UnknownEngine:
    @staticmethod
    def compute_wire_tools(local_path):
        return None


class _BoomEngine:
    @staticmethod
    def compute_wire_tools(local_path):
        raise RuntimeError("boom")


@pytest.mark.unit
def test_detect_returns_engine_verdict_true(monkeypatch):
    monkeypatch.setattr("src.core.config.LLM_Engine", _WireEngine)
    assert detect_wire_tools("/m/path") is True


@pytest.mark.unit
def test_detect_returns_engine_verdict_false(monkeypatch):
    monkeypatch.setattr("src.core.config.LLM_Engine", _NoWireEngine)
    assert detect_wire_tools("/m/path") is False


@pytest.mark.unit
def test_detect_passes_through_unknown(monkeypatch):
    monkeypatch.setattr("src.core.config.LLM_Engine", _UnknownEngine)
    assert detect_wire_tools("/m/path") is None


@pytest.mark.unit
def test_detect_none_when_engine_unset(monkeypatch):
    monkeypatch.setattr("src.core.config.LLM_Engine", None)
    assert detect_wire_tools("/m/path") is None


@pytest.mark.unit
def test_detect_none_when_path_empty(monkeypatch):
    monkeypatch.setattr("src.core.config.LLM_Engine", _WireEngine)
    assert detect_wire_tools("") is None
    assert detect_wire_tools(None) is None


@pytest.mark.unit
def test_detect_none_on_engine_failure(monkeypatch):
    # Detection must never block download finalization: a failing engine yields
    # None (column unset -> systematic routing), not an exception.
    monkeypatch.setattr("src.core.config.LLM_Engine", _BoomEngine)
    assert detect_wire_tools("/m/path") is None


# ---------------- unit: LLMResponse field ----------------


@pytest.mark.unit
def test_llmresponse_field_present_default_none():
    assert "supports_tools_wire" in LLMResponse.model_fields
    assert LLMResponse.model_fields["supports_tools_wire"].default is None


# ---------------- integration: column + round-trip ----------------


@pytest.mark.integration
def test_supports_tools_wire_column_exists(test_db_engine):
    cols = {c["name"] for c in sa_inspect(test_db_engine).get_columns("llms")}
    assert "supports_tools_wire" in cols


@pytest.mark.integration
def test_supports_tools_wire_roundtrip(test_db_session):
    llm = Llm(
        name="wire model",
        local=1,
        link="m/x",
        type="qwen",
        param_size=0.5,
        supports_tools=True,
        supports_tools_wire=True,
    )
    test_db_session.add(llm)
    test_db_session.commit()
    test_db_session.refresh(llm)
    assert llm.supports_tools_wire is True


@pytest.mark.integration
def test_supports_tools_wire_defaults_null(test_db_session):
    llm = Llm(name="pre-298 model", local=1, link="m/y", type="gemma", param_size=0.5)
    test_db_session.add(llm)
    test_db_session.commit()
    test_db_session.refresh(llm)
    assert llm.supports_tools_wire is None


@pytest.mark.integration
def test_llmresponse_serializes_supports_tools_wire_from_orm(test_db_session):
    llm = Llm(
        name="wire model",
        local=1,
        link="m/z",
        type="qwen",
        param_size=0.5,
        supports_tools_wire=False,
    )
    test_db_session.add(llm)
    test_db_session.commit()
    test_db_session.refresh(llm)
    resp = LLMResponse.model_validate(llm)
    assert resp.supports_tools_wire is False


# ---------------- integration: startup backfill ----------------


def _local_model(db, tmp_path, name, *, wire=None, local=1, with_dir=True):
    link = str(tmp_path / name)
    if with_dir:
        (tmp_path / name).mkdir()
    llm = Llm(
        name=name,
        local=local,
        link=link,
        type="qwen",
        param_size=0.5,
        supports_tools=True,
        supports_tools_wire=wire,
    )
    db.add(llm)
    db.commit()
    db.refresh(llm)
    return llm


@pytest.mark.integration
def test_backfill_persists_verdict_for_null_rows(test_db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("src.core.config.LLM_Engine", _WireEngine)
    llm = _local_model(test_db_session, tmp_path, "null-row")

    updated = Database_Seeder().backfill_wire_tools(test_db_session)
    test_db_session.refresh(llm)

    assert updated == 1
    assert llm.supports_tools_wire is True


@pytest.mark.integration
def test_backfill_leaves_unknown_verdicts_null(test_db_session, tmp_path, monkeypatch):
    # None verdict = detection unavailable -> stay NULL (retried next boot),
    # never pinned to False by a transient failure.
    monkeypatch.setattr("src.core.config.LLM_Engine", _UnknownEngine)
    llm = _local_model(test_db_session, tmp_path, "unknown-row")

    updated = Database_Seeder().backfill_wire_tools(test_db_session)
    test_db_session.refresh(llm)

    assert updated == 0
    assert llm.supports_tools_wire is None


@pytest.mark.integration
def test_backfill_skips_already_verified_and_remote_rows(test_db_session, tmp_path, monkeypatch):
    calls = []

    class _Counting:
        @staticmethod
        def compute_wire_tools(local_path):
            calls.append(local_path)
            return True

    monkeypatch.setattr("src.core.config.LLM_Engine", _Counting)
    verified = _local_model(test_db_session, tmp_path, "verified", wire=False)
    remote = _local_model(test_db_session, tmp_path, "remote", local=0)

    updated = Database_Seeder().backfill_wire_tools(test_db_session)
    test_db_session.refresh(verified)
    test_db_session.refresh(remote)

    assert updated == 0
    assert calls == []
    assert verified.supports_tools_wire is False  # untouched
    assert remote.supports_tools_wire is None


@pytest.mark.integration
def test_backfill_skips_missing_dir_without_crashing(test_db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("src.core.config.LLM_Engine", _WireEngine)
    orphan = _local_model(test_db_session, tmp_path, "orphan", with_dir=False)

    updated = Database_Seeder().backfill_wire_tools(test_db_session)
    test_db_session.refresh(orphan)

    assert updated == 0
    assert orphan.supports_tools_wire is None


@pytest.mark.integration
def test_backfill_survives_engine_failure(test_db_session, tmp_path, monkeypatch):
    # detect_wire_tools swallows the engine failure into None -> row stays NULL.
    monkeypatch.setattr("src.core.config.LLM_Engine", _BoomEngine)
    llm = _local_model(test_db_session, tmp_path, "boom-row")

    updated = Database_Seeder().backfill_wire_tools(test_db_session)
    test_db_session.refresh(llm)

    assert updated == 0
    assert llm.supports_tools_wire is None


@pytest.mark.integration
def test_backfill_computes_shared_links_once(test_db_session, tmp_path, monkeypatch):
    # A KB assistant shares its base model's link: one tokenizer load, two rows.
    calls = []

    class _Counting:
        @staticmethod
        def compute_wire_tools(local_path):
            calls.append(local_path)
            return True

    monkeypatch.setattr("src.core.config.LLM_Engine", _Counting)
    base = _local_model(test_db_session, tmp_path, "base")
    assistant = Llm(
        name="assistant",
        local=1,
        link=base.link,
        type="qwen",
        param_size=0.5,
        supports_tools=True,
        is_attached_to_kb=True,
    )
    test_db_session.add(assistant)
    test_db_session.commit()
    test_db_session.refresh(assistant)

    updated = Database_Seeder().backfill_wire_tools(test_db_session)
    test_db_session.refresh(base)
    test_db_session.refresh(assistant)

    assert updated == 2
    assert len(calls) == 1
    assert base.supports_tools_wire is True
    assert assistant.supports_tools_wire is True
