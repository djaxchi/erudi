"""Tests for persisting the supports_tools capability (issue #84, step 2).

- ``unit``: the ``detect_supports_tools`` helper (engine verdict, graceful None)
  and the ``LLMResponse`` field, fully mocked.
- ``integration``: the column exists on ``llms`` (the ALTER shim ran), a row
  round-trips, and ``LLMResponse`` surfaces it from the ORM.
"""
from __future__ import annotations

import pytest
from sqlalchemy import inspect as sa_inspect

from src.domains.llms.repository import detect_supports_tools
from src.domains.llms.schemas import LLMResponse
from src.entities.Llm import Llm


# ---------------- unit: detect_supports_tools helper ----------------


class _ToolEngine:
    @staticmethod
    def compute_supports_tools(local_path):
        return True


class _PlainEngine:
    @staticmethod
    def compute_supports_tools(local_path):
        return False


class _BoomEngine:
    @staticmethod
    def compute_supports_tools(local_path):
        raise RuntimeError("boom")


@pytest.mark.unit
def test_detect_returns_engine_verdict_true(monkeypatch):
    monkeypatch.setattr("src.core.config.LLM_Engine", _ToolEngine)
    assert detect_supports_tools("/m/path") is True


@pytest.mark.unit
def test_detect_returns_engine_verdict_false(monkeypatch):
    monkeypatch.setattr("src.core.config.LLM_Engine", _PlainEngine)
    assert detect_supports_tools("/m/path") is False


@pytest.mark.unit
def test_detect_none_when_engine_unset(monkeypatch):
    monkeypatch.setattr("src.core.config.LLM_Engine", None)
    assert detect_supports_tools("/m/path") is None


@pytest.mark.unit
def test_detect_none_when_path_empty(monkeypatch):
    monkeypatch.setattr("src.core.config.LLM_Engine", _ToolEngine)
    assert detect_supports_tools("") is None
    assert detect_supports_tools(None) is None


@pytest.mark.unit
def test_detect_none_on_engine_failure(monkeypatch):
    # Detection must never block download finalization: a failing engine yields
    # None (column unset), not an exception.
    monkeypatch.setattr("src.core.config.LLM_Engine", _BoomEngine)
    assert detect_supports_tools("/m/path") is None


# ---------------- unit: LLMResponse field ----------------


@pytest.mark.unit
def test_llmresponse_field_present_default_none():
    assert "supports_tools" in LLMResponse.model_fields
    assert LLMResponse.model_fields["supports_tools"].default is None


# ---------------- integration: column + round-trip ----------------


@pytest.mark.integration
def test_supports_tools_column_exists(test_db_engine):
    cols = {c["name"] for c in sa_inspect(test_db_engine).get_columns("llms")}
    assert "supports_tools" in cols


@pytest.mark.integration
def test_supports_tools_roundtrip_true(test_db_session):
    llm = Llm(name="tool model", local=1, link="m/x", type="qwen", param_size=0.5, supports_tools=True)
    test_db_session.add(llm)
    test_db_session.commit()
    test_db_session.refresh(llm)
    assert llm.supports_tools is True


@pytest.mark.integration
def test_supports_tools_defaults_null(test_db_session):
    llm = Llm(name="plain model", local=1, link="m/y", type="gemma", param_size=0.5)
    test_db_session.add(llm)
    test_db_session.commit()
    test_db_session.refresh(llm)
    assert llm.supports_tools is None


@pytest.mark.integration
def test_llmresponse_serializes_supports_tools_from_orm(test_db_session):
    llm = Llm(name="tool model", local=1, link="m/z", type="qwen", param_size=0.5, supports_tools=True)
    test_db_session.add(llm)
    test_db_session.commit()
    test_db_session.refresh(llm)
    resp = LLMResponse.model_validate(llm)
    assert resp.supports_tools is True
