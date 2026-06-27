"""Offline unit tests for the pure catalog classification helpers (#122).

These guard the signals that keep the Base catalog clean: derivative detection via
``base_model`` relation tags, instruct-vs-pretrain, capability categories (with the
'medium' != 'medical' boundary bug pinned), and real param sizing from safetensors
with a slug sanity-check. No network, no DB.
"""
import pytest

from src.database.catalog_classify import (
    categorize, is_derivative, is_instruct, param_size_billions,
    relation_targets, CAT_GENERAL, CAT_CODE, CAT_REASONING, CAT_MATH,
    CAT_VISION, CAT_MEDICAL, CAT_FUNCTION, CAT_SAFETY,
)


class TestRelationTags:
    def test_parses_relations(self):
        tags = ["base_model:quantized:mlx-community/foo-bf16",
                "base_model:finetune:Qwen/Qwen2.5-7B", "license:apache-2.0"]
        rel = relation_targets(tags)
        assert rel["quantized"] == ["mlx-community/foo-bf16"]
        assert rel["finetune"] == ["Qwen/Qwen2.5-7B"]
        assert "license" not in rel

    def test_handles_none(self):
        assert relation_targets(None) == {}


class TestIsDerivative:
    def test_quantized_merge_adapter_are_derivatives(self):
        assert is_derivative(["base_model:quantized:x/y"]) is True
        assert is_derivative(["base_model:merge:x/y"]) is True
        assert is_derivative(["base_model:adapter:x/y"]) is True

    def test_finetune_is_not_a_derivative(self):
        # Instruct releases tag themselves finetune of their pretrain — must stay base.
        assert is_derivative(["base_model:finetune:Qwen/Qwen2.5-7B"]) is False

    def test_no_tags(self):
        assert is_derivative([]) is False
        assert is_derivative(None) is False


class TestIsInstruct:
    @pytest.mark.parametrize("name,expected", [
        ("Qwen2.5-7B-Instruct", True),
        ("gemma-3-4b-it", True),
        ("DeepSeek-V3", True),            # suffix-less modern chat model kept
        ("gpt-oss-20b", True),
        ("Llama-3.1-8B", True),           # bare; family dedup (not this fn) prunes it
        ("gemma-2-9b-pt", False),         # pretrain marker
        ("Falcon3-7B-Base", False),
    ])
    def test_is_instruct(self, name, expected):
        assert is_instruct(name) is expected


class TestCategorize:
    @pytest.mark.parametrize("name,pipeline,expected", [
        ("Qwen2.5-7B-Instruct", "text-generation", CAT_GENERAL),
        ("Qwen2.5-Coder-7B-Instruct", "text-generation", CAT_CODE),
        ("DeepSeek-R1-Distill-Qwen-7B", "text-generation", CAT_REASONING),
        ("Phi-4-reasoning", "text-generation", CAT_REASONING),
        ("OpenReasoning-Nemotron-32B", "text-generation", CAT_REASONING),
        ("mathstral-7B-v0.1", "text-generation", CAT_MATH),
        ("Qwen2.5-VL-7B-Instruct", "image-text-to-text", CAT_VISION),
        ("gemma-4-31B-it", "any-to-any", CAT_VISION),
        ("medgemma-27b-text-it", "text-generation", CAT_MEDICAL),
        ("functiongemma-270m-it", "text-generation", CAT_FUNCTION),
        ("Llama-Guard-3-8B", "text-generation", CAT_SAFETY),
        ("gpt-oss-safeguard-20b", "text-generation", CAT_SAFETY),
    ])
    def test_categorize(self, name, pipeline, expected):
        assert categorize(name, [], pipeline) == expected

    def test_medium_is_not_medical(self):
        # 'Phi-3-medium' must NOT match the 'med' family (token-boundary, #122).
        assert categorize("Phi-3-medium-4k-instruct", [], "text-generation") == CAT_GENERAL

    def test_medical_beats_reasoning_order(self):
        # medgemma carries reasoning-ish tags but Medical is tested first.
        assert categorize("medgemma-27b-text-it", ["reasoning"], "text-generation") == CAT_MEDICAL

    def test_reasoning_via_tag(self):
        assert categorize("SomeModel-7B", ["reasoning"], "text-generation") == CAT_REASONING


class TestParamSize:
    def test_safetensors_preferred(self):
        assert param_size_billions(8_030_000_000, "Llama-3.1-8B-Instruct") == 8.03

    def test_slug_fallback_when_no_safetensors(self):
        assert param_size_billions(None, "Qwen2.5-7B-Instruct") == 7.0
        assert param_size_billions(None, "gemma-3-270m-it") == 0.27

    def test_slug_overrides_bogus_safetensors(self):
        # A "31B" assistant reporting 0.47B safetensors → trust the slug.
        assert param_size_billions(469_000_000, "gemma-4-31B-it-assistant") == 31.0

    def test_default_when_nothing(self):
        assert param_size_billions(None, "mystery-model") == 7.0
