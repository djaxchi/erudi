"""The GGUF-KV chat template route that replaced the transformers tokenizer (#313).

The point of these tests is PARITY plus the traps. Reading the template from the
GGUF header is only safe if the probes reach the same verdicts they did through
``AutoTokenizer``, and the ways it can silently go wrong are all about the Jinja
environment rather than the template: a missing global turns a rejection into a
successful render, which flips a verdict instead of raising.

Every test here drives the NEW route. A pin that exercises the old path proves
nothing about the code that now runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.engines.gguf_chat_template import (
    GgufChatTemplate,
    load_gguf_chat_template,
)
from src.engines.system_role_capability import tokenizer_supports_system_role
from src.engines.tool_capability import tokenizer_declares_tools

FIXTURES = Path(__file__).parent / "fixtures" / "chat_templates"


def _template(name: str) -> GgufChatTemplate:
    return GgufChatTemplate(
        chat_template=(FIXTURES / name).read_text(encoding="utf-8"),
        bos_token="<s>",
        eos_token="</s>",
    )


# ---------------- verdict parity on the known template matrix ----------------
# These are the same verdicts the transformers route produced; they are the
# contract this change must not move.


@pytest.mark.unit
@pytest.mark.parametrize(
    "fixture,supports_system,declares_tools",
    [
        ("gemma-2.jinja", False, False),
        ("gemma-3.jinja", True, False),
        ("qwen2.5-instruct.jinja", True, True),
    ],
)
def test_verdicts_match_the_tokenizer_route(fixture, supports_system, declares_tools):
    tpl = _template(fixture)
    assert tokenizer_supports_system_role(tpl) is supports_system
    assert tokenizer_declares_tools(tpl) is declares_tools


# ---------------- the traps: environment parity, not template text ----------------


@pytest.mark.unit
def test_gemma_rejects_system_through_raise_exception():
    """Gemma rejects the system role by CALLING raise_exception, so the global
    has to exist. Without it both renders fail, the differential reads
    'unrenderable', and the graceful default silently says True -- the fold then
    stops firing for the one model family it exists for."""
    tpl = _template("gemma-2.jinja")
    # user-only renders fine...
    assert tpl.apply_chat_template([{"role": "user", "content": "hi"}], add_generation_prompt=True)
    # ...and a system message is what breaks it.
    with pytest.raises(Exception, match="System role not supported"):
        tpl.apply_chat_template(
            [{"role": "system", "content": "x"}, {"role": "user", "content": "hi"}],
            add_generation_prompt=True,
        )


@pytest.mark.unit
def test_tojson_filter_is_available():
    """Qwen's tool block pipes signatures through ``tojson``. Missing filter =
    render failure = tool capability wrongly reported as absent."""
    tpl = _template("qwen2.5-instruct.jinja")
    out = tpl.apply_chat_template(
        [{"role": "user", "content": "hi"}],
        add_generation_prompt=True,
        tools=[{"type": "function", "function": {"name": "search"}}],
    )
    assert "search" in out


@pytest.mark.unit
def test_loopcontrols_extension_is_enabled():
    """``{% break %}`` is a COMPILE error without jinja2.ext.loopcontrols, which
    would read as 'unrenderable' rather than as a broken environment."""
    tpl = GgufChatTemplate(
        chat_template="{% for m in messages %}{{ m.content }}{% break %}{% endfor %}"
    )
    assert tpl.apply_chat_template([{"role": "user", "content": "hi"}]) == "hi"


@pytest.mark.unit
def test_bos_and_eos_tokens_are_bound():
    """Gemma's template references bos_token; an unbound name raises on use and
    would look like an unrenderable template."""
    tpl = GgufChatTemplate(
        chat_template="{{ bos_token }}|{{ eos_token }}", bos_token="<A>", eos_token="<B>"
    )
    assert tpl.apply_chat_template([]) == "<A>|<B>"


@pytest.mark.unit
def test_strftime_now_is_available():
    tpl = GgufChatTemplate(chat_template="{{ strftime_now('%Y') }}")
    assert tpl.apply_chat_template([]).isdigit()


@pytest.mark.unit
def test_template_rendering_is_sandboxed():
    """Chat templates ship inside downloaded GGUFs, so they are untrusted input."""
    tpl = GgufChatTemplate(chat_template="{{ ''.__class__.__mro__ }}")
    with pytest.raises(Exception):
        tpl.apply_chat_template([])


# ---------------- reading from a real artifact ----------------


@pytest.mark.unit
def test_missing_file_returns_none_and_never_raises():
    assert load_gguf_chat_template(Path("does") / "not" / "exist.gguf") is None


@pytest.mark.unit
def test_unreadable_artifact_returns_none(tmp_path):
    bogus = tmp_path / "not-really.gguf"
    bogus.write_bytes(b"not a gguf at all")
    assert load_gguf_chat_template(bogus) is None


@pytest.mark.unit
def test_no_transformers_import_on_the_probe_path(monkeypatch):
    """The whole point of #313: this path must not import transformers, whose
    native dependency chain deadlocks off the main thread in the frozen build."""
    import builtins

    real_import = builtins.__import__

    def guard(name, *args, **kwargs):
        if name.split(".")[0] == "transformers":
            raise AssertionError("probe path imported transformers")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guard)
    tpl = _template("qwen2.5-instruct.jinja")
    assert tokenizer_supports_system_role(tpl) is True
    assert tokenizer_declares_tools(tpl) is True
