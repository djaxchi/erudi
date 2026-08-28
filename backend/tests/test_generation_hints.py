"""Per-model sampling defaults (#388): capture of a base repo's generation facts
and the pure resolver that turns them into sampling defaults.

Precedence: curated profile > guarded HF generation_config > fallback constants.
A row without hints MUST resolve to today's constants (the #129-validated
request bodies stay byte-identical), and optional keys (top_k / min_p /
presence_penalty) exist only when a layer defines them.
"""
import json
import types
from unittest.mock import MagicMock

import pytest

from src.core import config
from src.database import generation_hints as gh
from src.database.generation_hints import (
    FALLBACK_MAX_TOKENS,
    FALLBACK_REPETITION_CONTEXT_SIZE,
    FALLBACK_REPETITION_PENALTY,
    FALLBACK_TEMPERATURE,
    FALLBACK_TOP_P,
    UNBOUNDED_CONTEXT_TOKENS,
    CuratedProfile,
    build_generation_hints,
    capture_generation_hints,
    read_local_generation_hints,
    resolve_base_repo,
    resolve_sampling_defaults,
)


class _Llm:
    def __init__(self, hints=None, type="qwen", link="mlx-community/Qwen3-0.6B-4bit",
                 name="Qwen3 0.6B"):
        self.generation_hints = hints
        self.type = type
        self.link = link
        self.name = name


class _MlxEngine:
    FORMAT_TAG = "mlx"

    @classmethod
    def max_context_tokens(cls):
        return None


class _LlamaEngine:
    FORMAT_TAG = "gguf"

    @classmethod
    def max_context_tokens(cls):
        return 4096


def _hints(**generation_config):
    return {
        "base_repo": "Qwen/Qwen3-0.6B",
        "generation_config": generation_config,
        "supports_thinking": True,
        "context_length": 40960,
        "captured_at": "2026-08-28",
    }


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    gh.reset_capture_cache()
    monkeypatch.setattr(config, "LLM_Engine", _MlxEngine)
    monkeypatch.setattr(gh, "SAMPLING_PROFILES", ())
    yield
    gh.reset_capture_cache()


# ---------------------------------------------------------------- resolver

class TestResolveFallback:
    def test_no_hints_resolves_to_todays_constants(self):
        d = resolve_sampling_defaults(_Llm(None))
        assert (d.temperature, d.top_p, d.max_tokens) == (
            FALLBACK_TEMPERATURE, FALLBACK_TOP_P, FALLBACK_MAX_TOKENS)
        assert (d.repetition_penalty, d.repetition_context_size) == (
            FALLBACK_REPETITION_PENALTY, FALLBACK_REPETITION_CONTEXT_SIZE)
        assert d.top_k is None and d.min_p is None and d.presence_penalty is None
        assert d.source == "fallback"
        assert d.base_repo is None

    def test_fallback_constants_are_the_129_values(self):
        # The #129 campaign validated 0.2 / 0.95 / 1024 + 1.1 x 64.
        assert (FALLBACK_TEMPERATURE, FALLBACK_TOP_P, FALLBACK_MAX_TOKENS) == (0.2, 0.95, 1024)
        assert (FALLBACK_REPETITION_PENALTY, FALLBACK_REPETITION_CONTEXT_SIZE) == (1.1, 64)

    def test_object_without_generation_hints_attribute_is_fallback(self):
        d = resolve_sampling_defaults(types.SimpleNamespace(type="x", link="y", name="z"))
        assert d.source == "fallback"

    def test_non_dict_hints_are_ignored(self):
        d = resolve_sampling_defaults(_Llm("garbage"))
        assert d.source == "fallback"

    def test_optional_keys_absent_from_wire_dict(self):
        wire = resolve_sampling_defaults(_Llm(None)).wire_kwargs()
        assert wire == {
            "repetition_penalty": FALLBACK_REPETITION_PENALTY,
            "repetition_context_size": FALLBACK_REPETITION_CONTEXT_SIZE,
        }


class TestResolveHfGenerationConfig:
    def test_qwen3_config_is_taken_as_shipped(self):
        d = resolve_sampling_defaults(
            _Llm(_hints(temperature=0.6, top_p=0.95, top_k=20, do_sample=True)))
        assert (d.temperature, d.top_p, d.top_k) == (0.6, 0.95, 20)
        assert d.min_p is None and d.presence_penalty is None
        assert d.source == "hf_generation_config"
        assert d.base_repo == "Qwen/Qwen3-0.6B"
        assert d.max_tokens == FALLBACK_MAX_TOKENS       # never taken from HF

    def test_wire_kwargs_carry_only_defined_optional_keys(self):
        wire = resolve_sampling_defaults(
            _Llm(_hints(temperature=0.7, top_k=20, min_p=0.0, presence_penalty=1.5,
                        repetition_penalty=1.05))).wire_kwargs()
        assert wire == {
            "repetition_penalty": 1.05,
            "repetition_context_size": FALLBACK_REPETITION_CONTEXT_SIZE,
            "top_k": 20,
            "min_p": 0.0,
            "presence_penalty": 1.5,
        }

    def test_per_key_fall_through(self):
        # Only temperature shipped: top_p keeps the fallback.
        d = resolve_sampling_defaults(_Llm(_hints(temperature=0.7)))
        assert d.temperature == 0.7
        assert d.top_p == FALLBACK_TOP_P
        assert d.source == "hf_generation_config"

    def test_do_sample_false_ignores_the_whole_block(self):
        d = resolve_sampling_defaults(
            _Llm(_hints(temperature=0.9, top_p=0.5, top_k=50, do_sample=False)))
        assert (d.temperature, d.top_p, d.top_k) == (FALLBACK_TEMPERATURE, FALLBACK_TOP_P, None)
        assert d.source == "fallback"

    def test_vendor_greedy_is_kept_as_shipped(self):
        # top_k == 1 / temperature < 0.05 means "the vendor says greedy": keep
        # exactly what ships (Qwen2.5-VL case), no second-guessing.
        d = resolve_sampling_defaults(_Llm(_hints(temperature=0.01, top_p=0.001, top_k=1)))
        assert (d.temperature, d.top_p, d.top_k) == (0.01, 0.001, 1)
        d = resolve_sampling_defaults(_Llm(_hints(temperature=0.0)))
        assert d.temperature == 0.0

    def test_clamps_and_drops_out_of_range_keys(self):
        d = resolve_sampling_defaults(
            _Llm(_hints(temperature=5.0, top_p=1.5, top_k=-3, min_p=2.0,
                        presence_penalty=9.0, repetition_penalty=-1)))
        assert d.temperature == 2.0                  # clamped
        assert d.top_p == FALLBACK_TOP_P             # (0, 1] violated -> dropped
        assert d.top_k is None and d.min_p is None and d.presence_penalty is None
        assert d.repetition_penalty == FALLBACK_REPETITION_PENALTY

    def test_non_numeric_values_are_dropped(self):
        d = resolve_sampling_defaults(_Llm(_hints(temperature="hot", top_k="many", top_p=None)))
        assert d.temperature == FALLBACK_TEMPERATURE
        assert d.top_k is None
        assert d.source == "fallback"

    def test_empty_block_is_fallback(self):
        d = resolve_sampling_defaults(_Llm(_hints()))
        assert d.source == "fallback"
        # Facts still ride along for the UI / cap even without sampling values.
        assert d.base_repo == "Qwen/Qwen3-0.6B"


class TestResolveCurated:
    def test_curated_profile_wins_over_hf(self, monkeypatch):
        monkeypatch.setattr(gh, "SAMPLING_PROFILES", (
            CuratedProfile(types=("qwen",), supports_thinking=True,
                           values={"temperature": 0.6, "top_k": 20, "presence_penalty": 1.5},
                           evidence="test"),
        ))
        d = resolve_sampling_defaults(_Llm(_hints(temperature=0.9, top_p=0.8, top_k=40)))
        assert d.temperature == 0.6
        assert d.top_k == 20
        assert d.presence_penalty == 1.5
        assert d.top_p == 0.8                        # not in the profile -> HF layer
        assert d.source == "curated"

    def test_curated_profile_matches_slug_pattern(self, monkeypatch):
        monkeypatch.setattr(gh, "SAMPLING_PROFILES", (
            CuratedProfile(slug_pattern=r"qwen3", values={"temperature": 0.7}, evidence="t"),
        ))
        assert resolve_sampling_defaults(_Llm(None)).source == "curated"
        assert resolve_sampling_defaults(
            _Llm(None, link="org/Llama-3.2-3B", name="Llama 3.2 3B")).source == "fallback"

    def test_thinking_flag_selects_the_thinking_profile(self, monkeypatch):
        monkeypatch.setattr(gh, "SAMPLING_PROFILES", (
            CuratedProfile(types=("qwen",), supports_thinking=True,
                           values={"temperature": 0.6}, evidence="t"),
            CuratedProfile(types=("qwen",), supports_thinking=False,
                           values={"temperature": 0.7}, evidence="t"),
        ))
        thinking = _hints(temperature=0.9)
        non_thinking = dict(thinking, supports_thinking=False)
        assert resolve_sampling_defaults(_Llm(thinking)).temperature == 0.6
        assert resolve_sampling_defaults(_Llm(non_thinking)).temperature == 0.7
        # Unknown thinking flag (no hints) matches neither profile.
        assert resolve_sampling_defaults(_Llm(None)).source == "fallback"

    def test_shipped_table_changes_nothing(self):
        # Repo rule: a curated entry needs an eval reference. The table ships
        # empty until the maintainer runs the #129-style campaign.
        assert gh.SAMPLING_PROFILES == () or all(p.evidence for p in gh.SAMPLING_PROFILES)


class TestMaxTokensCap:
    def test_unbounded_on_mlx_without_context_length(self):
        d = resolve_sampling_defaults(_Llm(None))
        assert d.max_tokens_cap == UNBOUNDED_CONTEXT_TOKENS

    def test_context_length_caps_on_mlx(self):
        d = resolve_sampling_defaults(_Llm(dict(_hints(), context_length=8192)))
        assert d.max_tokens_cap == 8192

    def test_engine_context_window_caps_on_llama_cpp(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_Engine", _LlamaEngine)
        assert resolve_sampling_defaults(_Llm(None)).max_tokens_cap == 4096
        assert resolve_sampling_defaults(
            _Llm(dict(_hints(), context_length=2048))).max_tokens_cap == 2048

    def test_max_tokens_never_exceeds_cap(self):
        d = resolve_sampling_defaults(_Llm(dict(_hints(), context_length=512)))
        assert d.max_tokens == 512

    def test_no_engine_selected_is_unbounded(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_Engine", None)
        assert resolve_sampling_defaults(_Llm(None)).max_tokens_cap == UNBOUNDED_CONTEXT_TOKENS

    def test_real_engines_expose_context_window(self, monkeypatch):
        from src.engines.base_engine import BaseEngine
        from src.engines.base_llama_cpp_engine import BaseLlamaCppEngine

        assert BaseEngine.max_context_tokens() is None
        monkeypatch.delenv("ERUDI_CTX", raising=False)
        assert BaseLlamaCppEngine.max_context_tokens() == 4096
        monkeypatch.setenv("ERUDI_CTX", "8192")
        assert BaseLlamaCppEngine.max_context_tokens() == 8192


class TestToDict:
    def test_to_dict_is_the_api_shape(self):
        d = resolve_sampling_defaults(_Llm(_hints(temperature=0.6, top_k=20))).to_dict()
        assert set(d) == {
            "temperature", "top_p", "max_tokens", "top_k", "min_p", "repetition_penalty",
            "repetition_context_size", "presence_penalty", "max_tokens_cap", "source",
            "base_repo",
        }


# ---------------------------------------------------------------- capture

class TestBuildGenerationHints:
    def test_whitelists_generation_config_keys(self):
        hints = build_generation_hints(
            base_repo="Qwen/Qwen3-0.6B",
            generation_config={"temperature": 0.6, "top_p": 0.95, "top_k": 20,
                               "do_sample": True, "bos_token_id": 1, "eos_token_id": [2, 3],
                               "transformers_version": "4.51"},
            config={"max_position_embeddings": 40960},
            chat_template="{% if enable_thinking %}...{% endif %}",
            captured_at="2026-08-28",
        )
        assert hints == {
            "base_repo": "Qwen/Qwen3-0.6B",
            "generation_config": {"temperature": 0.6, "top_p": 0.95, "top_k": 20,
                                  "do_sample": True},
            "supports_thinking": True,
            "context_length": 40960,
            "captured_at": "2026-08-28",
        }

    def test_nothing_captured_is_none(self):
        assert build_generation_hints(base_repo="x/y", generation_config=None,
                                      config=None, chat_template=None) is None

    def test_partial_capture_keeps_unknowns_none(self):
        hints = build_generation_hints(base_repo="x/y", generation_config={"temperature": 1.0},
                                       config=None, chat_template=None, captured_at="d")
        assert hints["context_length"] is None
        assert hints["supports_thinking"] is None
        assert hints["generation_config"] == {"temperature": 1.0}

    def test_context_length_from_nested_text_config(self):
        # VLM configs (Qwen2.5-VL) nest the text model's window.
        hints = build_generation_hints(
            base_repo="x/y", generation_config=None,
            config={"text_config": {"max_position_embeddings": 128000}},
            chat_template="plain", captured_at="d")
        assert hints["context_length"] == 128000
        assert hints["supports_thinking"] is False
        assert "generation_config" not in hints

    def test_chat_template_list_form(self):
        hints = build_generation_hints(
            base_repo="x/y", generation_config=None, config=None,
            chat_template=[{"name": "default", "template": "a"},
                           {"name": "think", "template": "{{ enable_thinking }}"}],
            captured_at="d")
        assert hints["supports_thinking"] is True


def _fake_hf_api(tmp_path, files):
    """hf_api stub whose hf_hub_download materializes ``files`` (name -> obj/str)."""
    api = MagicMock()

    def download(repo_id, filename, **_):
        if filename not in files:
            from huggingface_hub.errors import EntryNotFoundError
            raise EntryNotFoundError(f"{filename} missing")
        path = tmp_path / repo_id.replace("/", "__") / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = files[filename]
        path.write_text(payload if isinstance(payload, str) else json.dumps(payload),
                        encoding="utf-8")
        return str(path)

    api.hf_hub_download.side_effect = download
    return api


class TestCaptureGenerationHints:
    def test_captures_the_three_files(self, tmp_path):
        api = _fake_hf_api(tmp_path, {
            "generation_config.json": {"temperature": 0.6, "top_k": 20, "eos_token_id": 1},
            "config.json": {"max_position_embeddings": 40960},
            "tokenizer_config.json": {"chat_template": "{% if enable_thinking %}{% endif %}"},
        })
        hints = capture_generation_hints("Qwen/Qwen3-0.6B", api)
        assert hints["generation_config"] == {"temperature": 0.6, "top_k": 20}
        assert hints["context_length"] == 40960
        assert hints["supports_thinking"] is True
        assert hints["base_repo"] == "Qwen/Qwen3-0.6B"
        assert hints["captured_at"]
        called = {c.kwargs.get("filename") or c.args[1] for c in api.hf_hub_download.call_args_list}
        assert called == {"generation_config.json", "config.json", "tokenizer_config.json"}

    def test_missing_generation_config_still_captures_facts(self, tmp_path):
        api = _fake_hf_api(tmp_path, {"config.json": {"max_position_embeddings": 8192},
                                      "tokenizer_config.json": {"chat_template": "x"}})
        hints = capture_generation_hints("org/model", api)
        assert "generation_config" not in hints
        assert hints["context_length"] == 8192
        assert hints["supports_thinking"] is False

    def test_chat_template_jinja_fallback(self, tmp_path):
        api = _fake_hf_api(tmp_path, {"tokenizer_config.json": {},
                                      "chat_template.jinja": "{{ enable_thinking }}"})
        assert capture_generation_hints("org/model", api)["supports_thinking"] is True

    def test_all_missing_is_none(self, tmp_path):
        assert capture_generation_hints("org/model", _fake_hf_api(tmp_path, {})) is None

    def test_any_failure_is_none_never_raises(self):
        api = MagicMock()
        api.hf_hub_download.side_effect = RuntimeError("network died")
        assert capture_generation_hints("org/model", api) is None

    def test_gated_repo_is_none(self):
        from huggingface_hub.errors import GatedRepoError
        api = MagicMock()
        api.hf_hub_download.side_effect = GatedRepoError("403", response=MagicMock(status_code=403))
        assert capture_generation_hints("meta-llama/Llama-3.2-3B-Instruct", api) is None
        # Short-circuits: a gated repo is not probed three times.
        assert api.hf_hub_download.call_count == 1

    def test_no_api_or_repo_is_none(self):
        assert capture_generation_hints("org/model", None) is None
        assert capture_generation_hints("", MagicMock()) is None

    def test_memoized_per_base_repo(self, tmp_path):
        api = _fake_hf_api(tmp_path, {"config.json": {"max_position_embeddings": 1}})
        first = capture_generation_hints("org/model", api)
        second = capture_generation_hints("org/model", api)
        assert first == second
        # One pass (3 files + the chat_template.jinja fallback), not two.
        assert api.hf_hub_download.call_count == 4
        second["context_length"] = 999                   # copies, not shared state
        assert capture_generation_hints("org/model", api)["context_length"] == 1

    def test_failures_are_memoized_too(self):
        api = MagicMock()
        api.hf_hub_download.side_effect = RuntimeError("boom")
        capture_generation_hints("org/model", api)
        capture_generation_hints("org/model", api)
        assert api.hf_hub_download.call_count == 1

    def test_retrying_hf_api_exposes_hf_hub_download(self):
        # The capture rides the same retry wrapper as list_models/model_info.
        from src.core.config import _RetryingHfApi
        assert "hf_hub_download" in _RetryingHfApi.__dict__


class TestReadLocalGenerationHints:
    def test_reads_an_mlx_directory(self, tmp_path):
        (tmp_path / "generation_config.json").write_text(
            json.dumps({"temperature": 0.7, "top_p": 0.8, "pad_token_id": 0}), encoding="utf-8")
        (tmp_path / "config.json").write_text(
            json.dumps({"max_position_embeddings": 32768}), encoding="utf-8")
        (tmp_path / "tokenizer_config.json").write_text(
            json.dumps({"chat_template": "no thinking here"}), encoding="utf-8")
        hints = read_local_generation_hints(tmp_path, base_repo="mlx-community/x-4bit")
        assert hints["generation_config"] == {"temperature": 0.7, "top_p": 0.8}
        assert hints["context_length"] == 32768
        assert hints["supports_thinking"] is False
        assert hints["base_repo"] == "mlx-community/x-4bit"

    def test_gguf_directory_has_nothing(self, tmp_path):
        (tmp_path / "model.gguf").write_bytes(b"GGUF")
        assert read_local_generation_hints(tmp_path) is None

    def test_broken_json_is_none(self, tmp_path):
        (tmp_path / "generation_config.json").write_text("{not json", encoding="utf-8")
        assert read_local_generation_hints(tmp_path) is None

    def test_missing_directory_is_none(self, tmp_path):
        assert read_local_generation_hints(tmp_path / "nope") is None


class TestResolveBaseRepo:
    def test_first_base_model_relation_wins(self):
        tags = ["mlx", "base_model:quantized:Qwen/Qwen3-0.6B", "base_model:finetune:x/y"]
        assert resolve_base_repo("mlx-community/Qwen3-0.6B-4bit", tags) == "Qwen/Qwen3-0.6B"

    def test_without_relation_the_repo_itself(self):
        assert resolve_base_repo("org/model", ["mlx", "conversational"]) == "org/model"
        assert resolve_base_repo("org/model", None) == "org/model"
