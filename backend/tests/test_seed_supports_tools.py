"""Seed wires pre-download tool-calling detection onto catalog base models (#86).

The detection itself (HF chat-template differential render) is covered in
``test_tool_capability.py``; here we only assert the *wiring*: a seeded base
model carries the detected ``supports_tools`` so the catalog can recommend
agentic models before download. No network: the detector and metadata helpers
are stubbed.
"""
import pytest

from src.database import seed as seed_mod
from src.database.seed import Model_Config, Model_Seeder


class _FakeHF:
    def model_info(self, link):
        return object()


class _Size:
    def to_string(self):
        return "1 GB"


class _Engine:
    MODEL_MAPPING: dict = {}


def _stub_metadata_helpers(monkeypatch):
    # No engine is initialized in a unit context; seed reads MODEL_MAPPING off it.
    monkeypatch.setattr(seed_mod.config, "LLM_Engine", _Engine)
    monkeypatch.setattr(seed_mod, "format_model_info_metadata", lambda *a, **k: "meta")
    monkeypatch.setattr(seed_mod, "get_model_size_estimate", lambda *a, **k: _Size())
    monkeypatch.setattr(seed_mod, "get_disk_size_after_quant", lambda *a, **k: _Size())


@pytest.mark.unit
def test_base_model_seed_sets_supports_tools_from_hf(monkeypatch):
    captured = {}

    def fake_detect(link):
        captured["link"] = link
        return True

    monkeypatch.setattr(seed_mod, "tool_capability_from_hf_repo", fake_detect)
    _stub_metadata_helpers(monkeypatch)

    seeder = Model_Seeder(db=None, hf_api=_FakeHF())
    llm = seeder._create_base_llm(Model_Config("Test-7B", "org/test-7b", "test"))

    assert llm.supports_tools is True
    # Probes the actual link that would be downloaded (here unquantized == link).
    assert captured["link"] == "org/test-7b"


@pytest.mark.unit
def test_base_model_seed_leaves_supports_tools_none_when_unknown(monkeypatch):
    # Unreachable/gated repo -> detector returns None -> column stays unset
    # (never wrongly pinned to False before download).
    monkeypatch.setattr(seed_mod, "tool_capability_from_hf_repo", lambda link: None)
    _stub_metadata_helpers(monkeypatch)

    seeder = Model_Seeder(db=None, hf_api=_FakeHF())
    llm = seeder._create_base_llm(Model_Config("Test-7B", "org/test-7b", "test"))

    assert llm.supports_tools is None
