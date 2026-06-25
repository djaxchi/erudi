"""Catalog rows carry an ``is_base`` flag (#86).

base = curated foundation model (discovered from a FOUNDATION_ORG, built via
``_create_base_llm``/``_create_base_llm_fallback``); derived = community quant
(``_create_derived_llm``). The UI splits Base vs Community and recommends from
base on this flag — replacing a hand-maintained name list in the frontend.
No network here.
"""
import types

import pytest

from src.database import seed as seed_mod
from src.database.seed import Model_Config, Model_Seeder
from src.domains.llms.schemas import LLMResponse
from src.entities.Llm import Llm


class _FakeHF:
    def model_info(self, link):
        return object()


class _Size:
    def to_string(self):
        return "1 GB"


class _Engine:
    FORMAT_TAG = "gguf"


def _stub_metadata_helpers(monkeypatch):
    monkeypatch.setattr(seed_mod.config, "LLM_Engine", _Engine)
    monkeypatch.setattr(seed_mod, "format_model_info_metadata", lambda *a, **k: "meta")
    monkeypatch.setattr(seed_mod, "get_model_size_estimate", lambda *a, **k: _Size())
    monkeypatch.setattr(seed_mod, "get_disk_size_after_quant", lambda *a, **k: _Size())


@pytest.mark.unit
def test_base_creators_set_is_base_true(monkeypatch):
    _stub_metadata_helpers(monkeypatch)
    seeder = Model_Seeder(db=None, hf_api=_FakeHF())
    cfg = Model_Config("Test-7B", "org/test-7b", "test")

    assert seeder._create_base_llm(cfg, "quanter/test-7b-GGUF").is_base is True
    assert seeder._create_base_llm_fallback(cfg, "quanter/test-7b-GGUF").is_base is True


@pytest.mark.unit
def test_derived_creator_sets_is_base_false(monkeypatch):
    _stub_metadata_helpers(monkeypatch)
    seeder = Model_Seeder(db=None, hf_api=_FakeHF())
    model_info = types.SimpleNamespace(modelId="community/test-7b-GGUF")
    search_config = types.SimpleNamespace(model_type="test", default_param_size=7.0)

    assert seeder._create_derived_llm(model_info, search_config).is_base is False


@pytest.mark.unit
def test_offline_json_creator_sets_is_base_true():
    # The offline fallback seeds base models only — they must be marked base.
    seeder = Model_Seeder(db=None, hf_api=None)
    llm = seeder._create_base_llm_from_json(
        {"name": "Gemma 1B", "link": "google/gemma-3-1b-it", "type": "gemma",
         "param_size": 1.0, "model_metadata": "meta"}
    )
    assert llm.is_base is True


@pytest.mark.unit
def test_llm_response_exposes_is_base():
    # from_attributes surfaces the new column to the /remote endpoint automatically.
    llm = Llm(id=1, name="Test 7B", local=0, link="org/test-7b", type="test",
              param_size=7.0, is_base=True)
    resp = LLMResponse.model_validate(llm)
    assert resp.is_base is True
    assert "is_base" in resp.model_dump()
