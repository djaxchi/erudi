"""Static system-role capability detection.

A model supports a system role iff its chat template renders a leading system
message without raising. Gemma 2's template calls ``raise_exception('System role
not supported')``, which 500s every turn when we pass the system prompt as a real
system message; detecting it lets the runner fold the prompt into the first user
turn instead. Differential by design: a template that can't render at all is not
blamed on the system role.

- ``unit``: stub tokenizers (decision logic) + the real chat templates of a
  system-rejecting model (Gemma 2), a system-tolerant model (Gemma 3), and a
  system-supporting one (Qwen2.5), rendered through a minimal in-memory
  tokenizer. No weights, no network — runs on Linux CI.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.engines.system_role_capability import tokenizer_supports_system_role

FIXTURES = Path(__file__).parent / "fixtures" / "chat_templates"


class _SysStub:
    """``apply_chat_template`` stand-in keyed on whether a system message is present."""

    def __init__(self, *, raises_on_system: bool = False, raises_always: bool = False):
        self.raises_on_system = raises_on_system
        self.raises_always = raises_always

    def apply_chat_template(self, conversation, **kwargs):
        if self.raises_always:
            raise ValueError("template unrenderable")
        has_system = any(m.get("role") == "system" for m in conversation)
        if has_system and self.raises_on_system:
            raise ValueError("System role not supported")
        return "RENDER"


def _tokenizer_with_template(template: str):
    """A real ``PreTrainedTokenizerFast`` with the given chat template glued on
    (same approach as ``test_tool_capability``): renders real Jinja, no weights."""
    from tokenizers import Tokenizer, models
    from transformers import PreTrainedTokenizerFast

    backend = Tokenizer(
        models.WordLevel(vocab={"<s>": 0, "</s>": 1, "<unk>": 2}, unk_token="<unk>")
    )
    tok = PreTrainedTokenizerFast(
        tokenizer_object=backend, bos_token="<s>", eos_token="</s>", unk_token="<unk>"
    )
    tok.chat_template = template
    return tok


# ---------------- unit: decision logic ----------------


@pytest.mark.unit
def test_supports_when_system_renders():
    assert tokenizer_supports_system_role(_SysStub()) is True


@pytest.mark.unit
def test_not_supported_when_system_render_raises():
    assert tokenizer_supports_system_role(_SysStub(raises_on_system=True)) is False


@pytest.mark.unit
def test_assumes_supported_when_template_unrenderable():
    # User-only render already fails: not a system-role signal, don't fold.
    assert tokenizer_supports_system_role(_SysStub(raises_always=True)) is True


# ---------------- unit: real chat templates ----------------


@pytest.mark.unit
def test_real_gemma2_template_rejects_system_role():
    tok = _tokenizer_with_template((FIXTURES / "gemma-2.jinja").read_text())
    assert tokenizer_supports_system_role(tok) is False


@pytest.mark.unit
def test_real_gemma3_template_allows_system_role():
    tok = _tokenizer_with_template((FIXTURES / "gemma-3.jinja").read_text())
    assert tokenizer_supports_system_role(tok) is True


@pytest.mark.unit
def test_real_qwen_template_allows_system_role():
    tok = _tokenizer_with_template((FIXTURES / "qwen2.5-instruct.jinja").read_text())
    assert tokenizer_supports_system_role(tok) is True
