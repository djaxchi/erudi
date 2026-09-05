"""Web search agent tool (issue #310).

The tool wraps the ddgs metasearch library behind the same contract as
``search_knowledge_base``: async ``@tool``, hidden runtime context, bounded
attributed results, and a DETERMINISTIC dynamic error contract — the tool
NEVER raises; every failure returns text the model can read, prefixed
exactly ``Error during Web Search: `` with a cause-specific tail mapped
from the ddgs exception taxonomy. Empty results are NOT an error.
"""

from types import SimpleNamespace

import pytest
from ddgs.exceptions import DDGSException, RatelimitException, TimeoutException

from src.agents.tools import (
    TurnToolContext,
    WEB_SEARCH_ERROR_PREFIX,
    WEB_SEARCH_MAX_RESULTS,
    format_web_tool_result,
    map_web_search_error,
    web_search,
)

pytestmark = pytest.mark.unit


def _ctx(**kw):
    base = dict(web_max_results=5, web_token_budget=1000)
    base.update(kw)
    return TurnToolContext(**base)


def _runtime(ctx):
    # The tool only reads ``runtime.context`` — a namespace stands in for
    # ToolRuntime in direct-coroutine unit tests (the full agent round trip
    # is covered in test_agent_runner.py).
    return SimpleNamespace(context=ctx)


_RESULTS = [
    {
        "title": "Python 3.13 released",
        "href": "https://www.python.org/downloads/release/python-3130/",
        "body": "Python 3.13.0 is the newest major release of the Python language.",
    },
    {
        "title": "What's new in Python 3.13",
        "href": "https://docs.python.org/3/whatsnew/3.13.html",
        "body": "This article explains the new features in Python 3.13.",
    },
]


class TestTurnToolContext:
    def test_kb_fields_are_optional(self):
        ctx = TurnToolContext()
        assert ctx.kb_id is None
        assert ctx.kb_token_budget == 0

    def test_web_defaults(self):
        ctx = TurnToolContext()
        assert ctx.web_max_results == WEB_SEARCH_MAX_RESULTS
        assert ctx.web_token_budget > 0


class TestWebSearchToolSchema:
    def test_exposes_only_query_to_the_model(self):
        assert "query" in web_search.args
        assert "runtime" not in web_search.args

    def test_tool_name(self):
        assert web_search.name == "web_search"


class TestFormatWebToolResult:
    def test_results_are_attributed_with_source_urls(self):
        out = format_web_tool_result(_RESULTS, "latest python release", 1000)
        assert "Python 3.13 released - https://www.python.org/downloads/release/python-3130/" in out
        assert "Python 3.13.0 is the newest major release" in out
        assert "What's new in Python 3.13 - https://docs.python.org/3/whatsnew/3.13.html" in out

    def test_localized_answer_language_line_rides_last(self):
        out = format_web_tool_result(_RESULTS, "quelle est la dernière version de python ?", 1000)
        assert out.rstrip().endswith("Réponds en français.")

    def test_citation_reminder_present(self):
        out = format_web_tool_result(_RESULTS, "latest python release", 1000)
        assert "cite" in out.lower() and "url" in out.lower()

    def test_empty_results_is_not_an_error(self):
        out = format_web_tool_result([], "xyzzy", 1000)
        assert out == "No results found for this query."

    def test_token_budget_keeps_whole_results_best_first(self, monkeypatch):
        # Fake counter: 10 tokens per result — a 15-token budget keeps ONE.
        monkeypatch.setattr("src.agents.tools.count_tokens", lambda text: 10)
        out = format_web_tool_result(_RESULTS, "q", 15)
        assert "Python 3.13 released" in out
        assert "What's new in Python 3.13" not in out

    def test_first_result_survives_even_oversized(self, monkeypatch):
        monkeypatch.setattr("src.agents.tools.count_tokens", lambda text: 9999)
        out = format_web_tool_result(_RESULTS, "q", 100)
        assert "Python 3.13 released" in out


class TestWebSearchErrorMapping:
    """The locked deterministic contract: exact prefix + cause-specific tail."""

    def test_timeout(self):
        assert (
            map_web_search_error(TimeoutException("t"))
            == f"{WEB_SEARCH_ERROR_PREFIX}the request timed out"
        )

    def test_overall_guard_timeout(self):
        assert (
            map_web_search_error(TimeoutError("guard"))
            == f"{WEB_SEARCH_ERROR_PREFIX}the request timed out"
        )

    def test_ratelimit(self):
        assert map_web_search_error(RatelimitException("429")) == (
            f"{WEB_SEARCH_ERROR_PREFIX}search engines are rate-limiting requests, "
            "try again later"
        )

    def test_ddgs_wrapping_a_network_error_is_offline(self):
        exc = DDGSException("engine failed")
        exc.__cause__ = ConnectionError("dns fail")
        assert map_web_search_error(exc) == f"{WEB_SEARCH_ERROR_PREFIX}no internet connection"

    def test_bare_oserror_is_offline(self):
        assert (
            map_web_search_error(OSError("socket down"))
            == f"{WEB_SEARCH_ERROR_PREFIX}no internet connection"
        )

    def test_plain_ddgs_exception_is_unexpected_with_short_cause(self):
        out = map_web_search_error(DDGSException("parser exploded"))
        assert out.startswith(f"{WEB_SEARCH_ERROR_PREFIX}unexpected failure (")
        assert "parser exploded" in out

    def test_any_other_exception_is_unexpected(self):
        out = map_web_search_error(RuntimeError("boom"))
        assert out.startswith(f"{WEB_SEARCH_ERROR_PREFIX}unexpected failure (")
        assert "boom" in out

    def test_empty_message_falls_back_to_type_name(self):
        out = map_web_search_error(RuntimeError())
        assert "RuntimeError" in out


class TestWebSearchTool:
    async def test_returns_formatted_results(self, monkeypatch):
        calls = {}

        def fake_run(query, max_results):
            calls["query"] = query
            calls["max_results"] = max_results
            return _RESULTS

        monkeypatch.setattr("src.agents.tools._run_ddgs_text", fake_run)
        out = await web_search.coroutine(
            query="latest python release", runtime=_runtime(_ctx(web_max_results=3))
        )
        assert calls == {"query": "latest python release", "max_results": 3}
        assert "Python 3.13 released" in out
        assert "https://www.python.org" in out

    async def test_empty_results_returns_no_results_text(self, monkeypatch):
        monkeypatch.setattr("src.agents.tools._run_ddgs_text", lambda q, n: [])
        out = await web_search.coroutine(query="xyzzy", runtime=_runtime(_ctx()))
        assert out == "No results found for this query."

    @pytest.mark.parametrize(
        "exc,tail",
        [
            (TimeoutException("t"), "the request timed out"),
            (
                RatelimitException("429"),
                "search engines are rate-limiting requests, try again later",
            ),
            (ConnectionError("offline"), "no internet connection"),
        ],
    )
    async def test_never_raises_returns_mapped_error_text(self, monkeypatch, exc, tail):
        def boom(query, max_results):
            raise exc

        monkeypatch.setattr("src.agents.tools._run_ddgs_text", boom)
        out = await web_search.coroutine(query="q", runtime=_runtime(_ctx()))
        assert out == f"{WEB_SEARCH_ERROR_PREFIX}{tail}"

    async def test_unexpected_failure_never_raises(self, monkeypatch):
        def boom(query, max_results):
            raise ValueError("weird payload")

        monkeypatch.setattr("src.agents.tools._run_ddgs_text", boom)
        out = await web_search.coroutine(query="q", runtime=_runtime(_ctx()))
        assert out.startswith(f"{WEB_SEARCH_ERROR_PREFIX}unexpected failure (")
