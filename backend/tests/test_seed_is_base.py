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
def test_derived_creator_leaves_param_size_none_when_slug_has_no_size(monkeypatch):
    # A community slug with no size token used to be laundered into a plausible
    # default; now it stays unknown (#201) so the fit gauge can't rate it.
    _stub_metadata_helpers(monkeypatch)
    seeder = Model_Seeder(db=None, hf_api=_FakeHF())
    model_info = types.SimpleNamespace(modelId="community/mystery-model-GGUF")
    search_config = types.SimpleNamespace(model_type="test", default_param_size=7.0)

    llm = seeder._create_derived_llm(model_info, search_config)
    assert llm.param_size is None


@pytest.mark.unit
def test_llm_entity_accepts_none_param_size():
    # The validator must allow None (unknown) while still rejecting <= 0 (#201).
    assert Llm(name="x", local=0, link="org/x", type="test", param_size=None).param_size is None
    with pytest.raises(ValueError):
        Llm(name="y", local=0, link="org/y", type="test", param_size=0)


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


@pytest.mark.unit
def test_llm_response_exposes_conversational():
    # The IT-vs-base flag reaches the frontend so it can recommend chat models first (#182).
    llm = Llm(id=1, name="Test", local=0, link="org/test-it", type="test",
              param_size=7.0, is_base=True, conversational=True)
    resp = LLMResponse.model_validate(llm)
    assert resp.conversational is True
    assert "conversational" in resp.model_dump()


@pytest.mark.unit
def test_derived_creator_sets_conversational_from_signal(monkeypatch):
    # Community rows carry the chat flag so the UI can rank IT ones first (#182).
    _stub_metadata_helpers(monkeypatch)
    seeder = Model_Seeder(db=None, hf_api=_FakeHF())
    it = types.SimpleNamespace(modelId="cmty/Some-Model-Instruct-GGUF", tags=[],
                               pipeline_tag="text-generation")
    plain = types.SimpleNamespace(modelId="cmty/Some-Merge-GGUF",
                                  tags=["conversational"], pipeline_tag="text-generation")
    bare = types.SimpleNamespace(modelId="cmty/Some-Merge-GGUF", tags=[],
                                 pipeline_tag="text-generation")
    sc = types.SimpleNamespace(model_type="x", default_param_size=7.0)
    assert seeder._create_derived_llm(it, sc).conversational is True     # via suffix
    assert seeder._create_derived_llm(plain, sc).conversational is True  # via tag
    assert seeder._create_derived_llm(bare, sc).conversational is False  # neither


class _CommunityEngine:
    FORMAT_TAG = "gguf"

    @classmethod
    def community_search_kwargs(cls, term):
        kw = {"filter": cls.FORMAT_TAG}
        if term:
            kw["search"] = term
        return kw

    @staticmethod
    def is_runnable(_link):
        return True


@pytest.mark.unit
def test_build_derived_models_drops_nonchat_task_repos(monkeypatch):
    # #242: ASR / embedding / OCR community repos must not enter the catalog through
    # the search-driven derived path, while real chat/community finetunes survive.
    _stub_metadata_helpers(monkeypatch)
    monkeypatch.setattr(seed_mod.config, "LLM_Engine", _CommunityEngine)

    def mk(mid, pt):
        return types.SimpleNamespace(modelId=mid, downloads=100000, likes=50,
                                     tags=[], pipeline_tag=pt)

    hits = [
        mk("bartowski/Qwen3-8B-GGUF", "text-generation"),          # keep: chat
        mk("unsloth/gemma-4-12b-it-GGUF", "image-text-to-text"),   # keep: VLM chat (#122)
        mk("Qwen/Qwen3-Embedding-0.6B-GGUF", None),                # drop: embedding (name)
        mk("handy-computer/whisper-large-v3-gguf", "automatic-speech-recognition"),  # drop: ASR
        mk("mixedbread-ai/mxbai-embed-large-v1", "feature-extraction"),  # drop: embedding (pipeline)
        mk("ggml-org/DeepSeek-OCR-GGUF", None),                    # drop: OCR (name)
    ]
    api = types.SimpleNamespace(
        list_models=lambda **kw: list(hits),
        model_info=lambda link: object(),
    )
    seeder = Model_Seeder(db=None, hf_api=api)
    links = [m.link for m in
             seeder.build_derived_models([types.SimpleNamespace(search_term="", model_type="community")])]
    assert "bartowski/Qwen3-8B-GGUF" in links
    assert "unsloth/gemma-4-12b-it-GGUF" in links
    assert not any(x in " ".join(links).lower() for x in ("embed", "whisper", "ocr"))
