"""Tests for static tool-calling capability detection (issue #84, step 1).

Written before the implementation (TDD). A model supports tool calling iff
rendering its chat template WITH a probe tool differs from rendering it WITHOUT.
That is the exact signal the inference server reads (mlx-vlm / llama.cpp both
render the model's own chat template), so we read it statically from the
downloaded artifact: no inference, no runtime probe.

Sections:
- ``unit``: pure decision logic (stub tokenizer) + the real chat templates of
  a tool-capable (Qwen2.5) and a non-tool (Gemma 3) model, rendered through a
  minimal in-memory tokenizer (fixtures in ``tests/fixtures/chat_templates``).
  No model weights, no network, runs on Linux CI.
- ``mlx_only``: a real ``AutoTokenizer`` load on the downloaded MLX test model.

Run:
    pytest tests/test_tool_capability.py -m unit        # CI-friendly
    pytest tests/test_tool_capability.py -m mlx_only    # local Mac
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.engines.base_engine import BaseEngine
from src.engines.tool_capability import (
    tokenizer_declares_tools,
    tool_capability_from_hf_repo,
)

FIXTURES = Path(__file__).parent / "fixtures" / "chat_templates"


class _StubTokenizer:
    """Minimal ``apply_chat_template`` stand-in for decision-logic tests.

    ``declares`` controls whether passing ``tools`` changes the rendered text;
    the ``raises_*`` flags force a failure in either render call.
    """

    def __init__(self, *, declares: bool, raises_without: bool = False, raises_with: bool = False):
        self.declares = declares
        self.raises_without = raises_without
        self.raises_with = raises_with

    def apply_chat_template(self, conversation, tools=None, **kwargs):
        if tools is None:
            if self.raises_without:
                raise ValueError("boom-base")
            return "RENDER:base"
        if self.raises_with:
            raise ValueError("boom-tools")
        return "RENDER:base+tools" if self.declares else "RENDER:base"


def _minimal_tokenizer_with_template(template: str):
    """A real ``PreTrainedTokenizerFast`` with a 3-token vocab and the given
    chat template glued on. ``apply_chat_template(tokenize=False)`` only renders
    the Jinja, so the vocab is irrelevant: this exercises the real template with
    no model weights and no download."""
    from tokenizers import Tokenizer, models
    from transformers import PreTrainedTokenizerFast

    backend = Tokenizer(models.WordLevel(vocab={"<s>": 0, "</s>": 1, "<unk>": 2}, unk_token="<unk>"))
    tok = PreTrainedTokenizerFast(
        tokenizer_object=backend, bos_token="<s>", eos_token="</s>", unk_token="<unk>"
    )
    tok.chat_template = template
    return tok


# Test-only BaseEngine subclasses: a classmethod call never instantiates, so the
# other abstractmethods can stay unimplemented.
class _ToolCapableEngine(BaseEngine):
    @classmethod
    def _load_capability_tokenizer(cls, local_path):
        return _StubTokenizer(declares=True)


class _PlainEngine(BaseEngine):
    @classmethod
    def _load_capability_tokenizer(cls, local_path):
        return _StubTokenizer(declares=False)


class _BrokenEngine(BaseEngine):
    @classmethod
    def _load_capability_tokenizer(cls, local_path):
        raise RuntimeError("cannot load tokenizer")


class _NoneEngine(BaseEngine):
    @classmethod
    def _load_capability_tokenizer(cls, local_path):
        return None


# ---------------- unit: decision logic ----------------


@pytest.mark.unit
def test_declares_tools_true_when_render_differs():
    assert tokenizer_declares_tools(_StubTokenizer(declares=True)) is True


@pytest.mark.unit
def test_declares_tools_false_when_render_identical():
    assert tokenizer_declares_tools(_StubTokenizer(declares=False)) is False


@pytest.mark.unit
def test_declares_tools_false_when_tools_render_raises():
    # A template that rejects the tools kwarg is "not tool-capable", not a crash.
    assert tokenizer_declares_tools(_StubTokenizer(declares=True, raises_with=True)) is False


@pytest.mark.unit
def test_declares_tools_false_when_base_render_raises():
    assert tokenizer_declares_tools(_StubTokenizer(declares=True, raises_without=True)) is False


# ---------------- unit: real chat templates ----------------


@pytest.mark.unit
def test_real_qwen_template_supports_tools():
    tok = _minimal_tokenizer_with_template((FIXTURES / "qwen2.5-instruct.jinja").read_text())
    assert tokenizer_declares_tools(tok) is True


@pytest.mark.unit
def test_real_gemma_template_has_no_tools():
    tok = _minimal_tokenizer_with_template((FIXTURES / "gemma-3.jinja").read_text())
    assert tokenizer_declares_tools(tok) is False


# ---------------- unit: compute_supports_tools wiring + graceful fallback ----------------


@pytest.mark.unit
def test_compute_supports_tools_true():
    assert _ToolCapableEngine.compute_supports_tools("/any/path") is True


@pytest.mark.unit
def test_compute_supports_tools_false():
    assert _PlainEngine.compute_supports_tools("/any/path") is False


@pytest.mark.unit
def test_compute_supports_tools_graceful_on_load_failure():
    # A model whose capability cannot be read must fall back to False so the
    # turn routes through the systematic KB path (never lose the feature).
    assert _BrokenEngine.compute_supports_tools("/any/path") is False


@pytest.mark.unit
def test_compute_supports_tools_graceful_on_none_tokenizer():
    assert _NoneEngine.compute_supports_tools("/any/path") is False


# ---------------- unit: pre-download detection from a HF repo (#84/#86) ----------------


@pytest.mark.unit
def test_hf_repo_tool_capable(monkeypatch):
    tok = _minimal_tokenizer_with_template((FIXTURES / "qwen2.5-instruct.jinja").read_text())
    monkeypatch.setattr("transformers.AutoTokenizer.from_pretrained", lambda *a, **k: tok)
    assert tool_capability_from_hf_repo("org/qwen-like") is True


@pytest.mark.unit
def test_hf_repo_not_tool_capable(monkeypatch):
    tok = _minimal_tokenizer_with_template((FIXTURES / "gemma-3.jinja").read_text())
    monkeypatch.setattr("transformers.AutoTokenizer.from_pretrained", lambda *a, **k: tok)
    assert tool_capability_from_hf_repo("org/gemma-like") is False


@pytest.mark.unit
def test_hf_repo_none_on_load_failure(monkeypatch):
    # Pre-download we never assume a capability we could not probe: an
    # unreachable/gated repo yields None (unknown), NOT False.
    def boom(*a, **k):
        raise OSError("repo not found / gated")

    monkeypatch.setattr("transformers.AutoTokenizer.from_pretrained", boom)
    assert tool_capability_from_hf_repo("org/missing") is None


@pytest.mark.unit
def test_hf_repo_none_on_empty_repo_id():
    assert tool_capability_from_hf_repo("") is None


# ---------------- mlx_only: real tokenizer load ----------------


@pytest.mark.mlx_only
def test_compute_supports_tools_real_mlx(mlx_test_model_path):
    # The session fixture downloads Qwen2.5-0.5B-Instruct-4bit (tool-capable).
    from src.engines.mlx_engine import MLX_Engine

    assert MLX_Engine.compute_supports_tools(mlx_test_model_path) is True
