"""Offline unit tests for the base→quant resolver (no network).

Reliability of the resolver is the linchpin of the auto-catalog: every base model
must resolve to its EXACT engine-format quant, or to None (then it just doesn't
appear). These tests pin the normalization rules and the exact-match selection
against a mocked HF api, covering the real tricky cases the research surfaced
(gpt-oss MXFP4, vendor-prefixed GGUF names, version confusion, slug ambiguity).
"""

import os

import pytest

from src.engines.model_resolver import normalize, base_key, resolve_quant


class _Model:
    def __init__(self, mid, downloads=0):
        self.id = mid
        self.downloads = downloads


class _FakeApi:
    """Returns a fixed candidate list regardless of query (we test selection)."""
    def __init__(self, ids):
        self._models = [_Model(i, d) for i, d in ids]

    def list_models(self, **kwargs):
        return list(self._models)


class _BoomApi:
    def list_models(self, **kwargs):
        raise RuntimeError("network down")


class TestNormalize:
    @pytest.mark.parametrize("name,owner,expected", [
        ("gemma-3-1b-it-4bit", "google", "gemma-3-1b-it"),
        ("gemma-2-2b-it-4bit", "google", "gemma-2-2b-it"),
        ("google_gemma-3-1b-it-GGUF", "google", "gemma-3-1b-it"),   # vendor prefix in name
        ("gpt-oss-20b-MXFP4-Q8", "openai", "gpt-oss-20b"),          # multi-token format tail
        ("Qwen_Qwen3-4B-GGUF", "Qwen", "qwen3-4b"),                 # cross-org vendor prefix
        ("internlm2_5-20b-chat_8bit", "internlm", "internlm2-5-20b-chat"),  # underscores
        ("Mistral-Small-3.2-24B-Instruct-2506-bf16", "mistralai", "mistral-small-3.2-24b-instruct-2506"),
        ("DeepSeek-V3-4bit", "deepseek-ai", "deepseek-v3"),
        ("SmolLM2-1.7B-Instruct", "HuggingFaceTB", "smollm2-1.7b-instruct"),  # no quant suffix
    ])
    def test_normalize(self, name, owner, expected):
        assert normalize(name, owner) == expected

    def test_does_not_strip_real_slug_tokens(self):
        # qat / preview / instruct are part of real slugs, never stripped
        assert normalize("gemma-3-1b-it-qat-4bit", "google") == "gemma-3-1b-it-qat"
        assert normalize("granite-3.2-8b-instruct-preview-4bit", "ibm-granite") == "granite-3.2-8b-instruct-preview"

    def test_base_key(self):
        assert base_key("google/gemma-2-2b-it") == "gemma-2-2b-it"
        assert base_key("openai/gpt-oss-20b") == "gpt-oss-20b"


class TestResolveQuant:
    def test_picks_exact_over_higher_download_wrong_model(self):
        # The classic trap: gemma-4-e2b outranks gemma-2-2b by downloads, but the
        # exact-normalized rule must still pick gemma-2-2b.
        api = _FakeApi([
            ("mlx-community/gemma-4-e2b-it-4bit", 83321),
            ("mlx-community/gemma-2-2b-it-4bit", 5889),
            ("mlx-community/gemma-4-e2b-it-bf16", 1801),
        ])
        assert resolve_quant("google/gemma-2-2b-it", "mlx", api) == "mlx-community/gemma-2-2b-it-4bit"

    def test_prefers_4bit_among_exacts(self):
        api = _FakeApi([
            ("mlx-community/gpt-oss-20b-MXFP4-Q8", 397624),
            ("mlx-community/gpt-oss-20b-OptiQ-4bit", 294),  # not exact (OptiQ token remains)
            ("mlx-community/gpt-oss-20b-mxfp4-bf16", 414),
        ])
        # All real exacts are MXFP4 variants → highest downloads wins (no -4bit present).
        assert resolve_quant("openai/gpt-oss-20b", "mlx", api) == "mlx-community/gpt-oss-20b-MXFP4-Q8"

    def test_rejects_version_siblings(self):
        api = _FakeApi([
            ("mlx-community/DeepSeek-V3.1-4bit", 6385),
            ("mlx-community/DeepSeek-V3-0324-4bit", 1830),
            ("mlx-community/DeepSeek-V3-4bit", 826),
        ])
        assert resolve_quant("deepseek-ai/DeepSeek-V3", "mlx", api) == "mlx-community/DeepSeek-V3-4bit"

    def test_none_when_no_exact_match(self):
        # Only finetunes / siblings present, no exact base quant → None (won't appear).
        api = _FakeApi([
            ("someone/Phi-4-mini-instruct-4bit", 9999),
            ("other/Phi-4-reasoning-4bit", 5000),
        ])
        assert resolve_quant("microsoft/phi-4", "mlx", api) is None

    def test_vendor_prefixed_gguf_name_matches(self):
        api = _FakeApi([("bartowski/google_gemma-3-1b-it-GGUF", 12345)])
        assert resolve_quant("google/gemma-3-1b-it", "gguf", api) == "bartowski/google_gemma-3-1b-it-GGUF"

    def test_network_failure_returns_none(self):
        assert resolve_quant("google/gemma-3-1b-it", "mlx", _BoomApi()) is None


# Ground truth from the HF research sweep: (base_id, format_tag, quant_known_to_exist).
# Mix of clean cases and the documented tricky ones, both engines.
_GROUND_TRUTH = [
    ("google/gemma-2-2b-it", "mlx", True),
    ("google/gemma-3-1b-it", "mlx", True),
    ("Qwen/Qwen3-8B", "mlx", True),
    ("Qwen/Qwen2.5-7B-Instruct", "mlx", True),
    ("meta-llama/Llama-3.1-8B-Instruct", "mlx", True),
    ("openai/gpt-oss-20b", "mlx", True),
    ("microsoft/phi-4", "mlx", True),
    ("microsoft/Phi-4-mini-instruct", "mlx", True),
    ("mistralai/Mistral-Nemo-Instruct-2407", "mlx", True),
    ("deepseek-ai/DeepSeek-R1-Distill-Qwen-7B", "mlx", True),
    ("zai-org/GLM-4-9B-0414", "mlx", True),
    ("ibm-granite/granite-4.1-8b", "mlx", True),
    ("google/gemma-3-1b-it", "gguf", True),
    ("Qwen/Qwen3-4B", "gguf", True),
    ("mistralai/Mistral-7B-Instruct-v0.3", "gguf", True),
    ("meta-llama/Llama-3.3-70B-Instruct", "gguf", True),
    ("openai/gpt-oss-20b", "gguf", True),
    ("deepseek-ai/DeepSeek-V3", "gguf", True),
    ("tiiuae/Falcon3-7B-Instruct", "gguf", True),
    ("CohereLabs/c4ai-command-r7b-12-2024", "gguf", True),
]


@pytest.mark.network
@pytest.mark.skipif(not os.environ.get("ERUDI_TEST_NETWORK"),
                    reason="hits live HF; set ERUDI_TEST_NETWORK=1")
class TestResolverLiveEval:
    """Anti-regression guard against the REAL HF API: the resolver must never pick
    a wrong model (every non-None result is an exact normalized match), and overall
    coverage must stay high (catches a broad HF rename/removal that breaks resolution).
    """

    def _api(self):
        from huggingface_hub import HfApi
        return HfApi(token=None)

    def test_no_wrong_picks_and_high_coverage(self):
        api = self._api()
        resolved = misses = 0
        wrong = []
        for base_id, tag, exists in _GROUND_TRUTH:
            got = resolve_quant(base_id, tag, api)
            if got is None:
                if exists:
                    misses += 1
                continue
            resolved += 1
            # SAFETY invariant: a non-None result is ALWAYS the right model.
            if normalize(got.split("/")[-1], base_id.split("/")[0]) != base_key(base_id):
                wrong.append((base_id, tag, got))
        assert not wrong, f"resolver returned wrong models: {wrong}"
        total_existing = sum(1 for _, _, e in _GROUND_TRUTH if e)
        coverage = resolved / total_existing
        assert coverage >= 0.85, f"coverage dropped to {coverage:.0%} ({misses} misses)"

