"""The catalog build path does NOT do pre-download tool detection (#113).

Downloading a tokenizer per catalog model to render the chat template was not
viable at catalog scale (~150 downloads dominating the resync). It is dropped:
remote catalog entries keep ``supports_tools = null`` and detection happens
post-download (where the tokenizer is already on disk). No network here.
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
    FORMAT_TAG = "gguf"


def _stub_metadata_helpers(monkeypatch):
    monkeypatch.setattr(seed_mod.config, "LLM_Engine", _Engine)
    monkeypatch.setattr(seed_mod, "format_model_info_metadata", lambda *a, **k: "meta")
    monkeypatch.setattr(seed_mod, "get_model_size_estimate", lambda *a, **k: _Size())
    monkeypatch.setattr(seed_mod, "get_disk_size_after_quant", lambda *a, **k: _Size())


@pytest.mark.unit
def test_base_model_seed_does_not_pre_detect_tools(monkeypatch):
    _stub_metadata_helpers(monkeypatch)
    seeder = Model_Seeder(db=None, hf_api=_FakeHF())

    base = seeder._create_base_llm(
        Model_Config("Test-7B", "org/test-7b", "test"), "quanter/test-7b-GGUF"
    )
    fallback = seeder._create_base_llm_fallback(
        Model_Config("Test-7B", "org/test-7b", "test"), "quanter/test-7b-GGUF"
    )

    # Pre-download detection dropped (#113): no tokenizer download, column stays null.
    assert base.supports_tools is None
    assert fallback.supports_tools is None


@pytest.mark.unit
def test_seed_module_no_longer_imports_the_tokenizer_detector():
    # The catalog build path must not pull the tokenizer-download detector at all.
    assert not hasattr(seed_mod, "tool_capability_from_hf_repo")
