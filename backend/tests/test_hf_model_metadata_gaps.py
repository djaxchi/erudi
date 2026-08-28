"""Gap coverage for `src.utils.hf_model_metadata` size estimation paths.

Pins the API-backed disk size with its estimate fallbacks per quantization
tier, the family pattern tables (Mistral/Gemma/Qwen), the chosen-artifact
byte accounting (#170/#220) for GGUF multi-quant vs single-artifact repos,
and the metadata formatter's shape and error path.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.core import config
from src.utils import hf_model_metadata as meta
from src.utils.hf_model_metadata import (
    ModelSize,
    QuantizationType,
    _chosen_artifact_bytes,
    format_model_info_metadata,
    get_disk_size_after_quant,
    get_model_size_estimate,
)


def _repo_info(files):
    return SimpleNamespace(
        siblings=[SimpleNamespace(rfilename=f, size=s) for f, s in files]
    )


class _NonGgufEngine:
    USES_GGUF = False


class _GgufEngine:
    USES_GGUF = True


# =====================================================================
# UNIT - get_disk_size_after_quant
# =====================================================================

@pytest.mark.unit
class TestDiskSizeAfterQuant:

    def test_api_success_sums_chosen_artifacts(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_Engine", _NonGgufEngine)
        api = MagicMock()
        # Decimal GB (#316): the unit Hugging Face quotes for the same files.
        api.repo_info.return_value = _repo_info(
            [("model.safetensors", 2 * 1_000_000_000), ("config.json", 1024)]
        )
        monkeypatch.setattr(meta, "get_hf_api", lambda: api)
        size = get_disk_size_after_quant("mlx-community/Some-Model-4bit")
        assert size.is_estimate is False
        assert size.source == "api"
        assert size.size_gb == pytest.approx(2.0, abs=0.01)

    def _fail_api(self, monkeypatch):
        api = MagicMock()
        api.repo_info.side_effect = RuntimeError("HF down")
        monkeypatch.setattr(meta, "get_hf_api", lambda: api)

    def test_fallback_estimates_from_parameter_pattern(self, monkeypatch):
        self._fail_api(monkeypatch)
        size = get_disk_size_after_quant("mlx-community/Some-Model-7B-4bit")
        assert size.is_estimate is True
        assert size.size_gb > 0

    def test_fallback_int4_default_seven_b(self, monkeypatch):
        self._fail_api(monkeypatch)
        # '4-bit' (with the dash) marks INT4 without matching the '4b'
        # parameter token, forcing the hard fallback branch.
        size = get_disk_size_after_quant("someone/mystery-4-bit")
        assert size.source == "fallback"
        assert size.size_gb == 3.5

    @pytest.mark.parametrize("repo,expected_gb", [
        ("someone/tiny-1b-8bit", 1.5),
        ("someone/small-2b-8bit", 2.5),
        ("someone/mid-4b-8bit", 4.5),
    ])
    def test_fallback_int8_size_hints(self, monkeypatch, repo, expected_gb):
        self._fail_api(monkeypatch)
        size = get_disk_size_after_quant(repo)
        # A size token in the id may be picked up by the parameter-pattern
        # calculation first; either way the estimate must land in the hinted
        # ballpark rather than the 7B default.
        assert size.is_estimate is True
        assert 0 < size.size_gb <= expected_gb + 2.0

    def test_fallback_int8_default(self, monkeypatch):
        self._fail_api(monkeypatch)
        size = get_disk_size_after_quant("someone/mystery-8-bit")
        assert size.source == "fallback"
        assert size.size_gb == 7.0

    def test_fallback_unknown_quant_is_zero(self, monkeypatch):
        self._fail_api(monkeypatch)
        size = get_disk_size_after_quant("someone/mystery-model")
        assert size.source == "unknown"
        assert size.size_gb == 0.0

    def test_api_success_carries_the_exact_artifact_bytes(self, monkeypatch):
        """The real download size, in bytes, rides on the ModelSize so the catalog
        can store it as-is (no GB round-trip) next to the display string."""
        monkeypatch.setattr(config, "LLM_Engine", _GgufEngine)
        api = MagicMock()
        api.repo_info.return_value = _repo_info([
            ("model-q4_k_m.gguf", 3_074_000_000),
            ("model-q8_0.gguf", 8_000_000_000),
            ("config.json", 1024),
        ])
        monkeypatch.setattr(meta, "get_hf_api", lambda: api)
        size = get_disk_size_after_quant("someone/model-GGUF")
        assert size.size_bytes == 3_074_000_000 + 1024   # the chosen quant + aux, not the repo
        assert size.size_gb == pytest.approx(size.size_bytes / 1_000_000_000)

    def test_estimates_never_claim_exact_bytes(self, monkeypatch):
        self._fail_api(monkeypatch)
        assert get_disk_size_after_quant("mlx-community/Some-Model-7B-4bit").size_bytes is None
        assert get_disk_size_after_quant("someone/mystery-model").size_bytes is None
        assert ModelSize(size_gb=1.0).size_bytes is None

    def test_uses_the_injected_client_over_the_global_one(self, monkeypatch):
        """The seeder passes its own (retrying, or stubbed) client so a catalog
        build never opens a second session through the module-level factory."""
        monkeypatch.setattr(config, "LLM_Engine", _NonGgufEngine)
        monkeypatch.setattr(meta, "get_hf_api", lambda: pytest.fail("global client used"))
        api = MagicMock()
        api.repo_info.return_value = _repo_info([("model.safetensors", 2_000_000_000)])
        size = get_disk_size_after_quant("mlx-community/Some-Model-4bit", hf_api=api)
        assert size.size_bytes == 2_000_000_000
        api.repo_info.assert_called_once_with("mlx-community/Some-Model-4bit", files_metadata=True)

    def test_injected_client_without_repo_info_falls_back_to_the_estimate(self, monkeypatch):
        # A bare stub (as the seeder tests inject) must degrade to an estimate,
        # never reach the network through the global factory.
        monkeypatch.setattr(meta, "get_hf_api", lambda: pytest.fail("global client used"))
        size = get_disk_size_after_quant("someone/Some-7B-4bit", hf_api=SimpleNamespace())
        assert size.is_estimate is True
        assert size.size_bytes is None


# =====================================================================
# UNIT - get_model_size_estimate family patterns
# =====================================================================

@pytest.mark.unit
class TestModelSizeEstimate:

    def test_exact_map_match(self):
        link = next(iter(meta.MODEL_SIZE_MAP))
        size = get_model_size_estimate("whatever", link)
        assert size.source == "map"
        assert size.size_gb == meta.MODEL_SIZE_MAP[link][0]

    @pytest.mark.parametrize("name,link,expected_gb", [
        ("Mistral 7B", "user/custom-mistral-7b", 13.5),
        ("Gemma 1B", "user/gemma-1b-ft", 2.5),
        ("Gemma 2B", "user/gemma-2b-ft", 5.5),
        ("Gemma 4 E2B", "user/gemma-4-e2b-ft", 5.0),
        ("Gemma 4B", "user/gemma-3-4b-ft", 9.0),
        ("Gemma 7B", "user/gemma-7b-ft", 13.5),
        ("Qwen 0.5B", "user/qwen-0.5b-ft", 1.0),
        ("Qwen 1.5B", "user/qwen-1.5b-ft", 3.0),
        ("Qwen 3B", "user/qwen-3b-ft", 6.5),
        ("Qwen 7B", "user/qwen-7b-ft", 14.5),
    ])
    def test_family_patterns(self, name, link, expected_gb):
        size = get_model_size_estimate(name, link)
        assert size.source == "pattern"
        assert size.size_gb == expected_gb

    def test_unknown_family_calculates_from_parameters(self):
        size = get_model_size_estimate("Falcon 7B", "tiiuae/falcon-7b")
        assert size.size_gb > 0
        assert size.is_estimate is True

    def test_no_signal_returns_unknown(self):
        size = get_model_size_estimate("Mystery", "user/mystery-model")
        assert size.source == "unknown"
        assert size.size_gb == 0.0


# =====================================================================
# UNIT - chosen-artifact byte accounting (#170/#220)
# =====================================================================

@pytest.mark.unit
class TestChosenArtifactBytes:

    def test_gguf_repo_counts_single_best_quant(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_Engine", _GgufEngine)
        repo = _repo_info([
            ("model-q4_k_m.gguf", 2 * 1024**3),
            ("model-q8_0.gguf", 4 * 1024**3),
            ("model-f16.gguf", 14 * 1024**3),
            ("config.json", 1024),
        ])
        total = _chosen_artifact_bytes(repo)
        # Single q4_k_m + small aux, NOT the 20 GB whole-repo sum
        assert total < 3 * 1024**3
        assert total >= 2 * 1024**3

    def test_non_gguf_repo_counts_everything(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_Engine", _NonGgufEngine)
        repo = _repo_info([
            ("model-00001.safetensors", 3 * 1024**3),
            ("model-00002.safetensors", 3 * 1024**3),
        ])
        assert _chosen_artifact_bytes(repo) == 6 * 1024**3

    def test_gguf_repo_without_gguf_falls_back_to_whole_repo(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_Engine", _GgufEngine)
        repo = _repo_info([("weights.bin", 5 * 1024**3)])
        assert _chosen_artifact_bytes(repo) == 5 * 1024**3


# =====================================================================
# UNIT - metadata formatter
# =====================================================================

@pytest.mark.unit
class TestFormatModelInfoMetadata:

    def _info(self, **overrides):
        data = dict(
            id="org/model-7b",
            author="org",
            created_at="2026-01-01",
            downloads=1000,
            likes=42,
            library_name="transformers",
            pipeline_tag="text-generation",
            private=False,
            gated=False,
            tags=["tag-" + str(i) for i in range(12)],
            sha="abc123",
            last_modified="2026-02-01",
        )
        data.update(overrides)
        return SimpleNamespace(**data)

    def test_full_shape_with_tag_truncation(self):
        size = ModelSize(size_gb=13.5, min_gb=13.0, max_gb=14.0,
                         is_estimate=True, source="pattern")
        out = format_model_info_metadata(self._info(), size, quantized=True)
        assert "Model ID: org/model-7b" in out
        assert "Quantized: True" in out
        assert "Parameters: 7" in out
        assert "tag-9" in out and "tag-10" not in out  # first 10 only
        assert out.rstrip().endswith("2026-02-01")

    def test_missing_fields_default_to_unknown(self):
        out = format_model_info_metadata(
            self._info(author=None, library_name=None, tags=[], sha=None),
            size_estimate=None,
        )
        assert "Author: Unknown" in out
        assert "Size: Unknown" in out
        assert "Tags: None" in out

    def test_formatting_failure_returns_error_string(self):
        out = format_model_info_metadata(SimpleNamespace())  # no .id attribute
        assert out.startswith("Error formatting metadata")
