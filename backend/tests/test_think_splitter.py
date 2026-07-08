"""Unit matrix for the streaming ``<think>`` splitter (issue #90).

Adversarial split coverage: tags mid-chunk, split across 2 and 3 chunks, one char
at a time, unclosed tags at stream end, and false-alarm partials. The invariant
under test: text inside ``<think>...</think>`` becomes ``thinking`` events,
everything else becomes ``answer`` events, and reasoning NEVER leaks into answer
text regardless of how the stream is chopped.
"""
import pytest

from src.agents.think_splitter import ThinkSplitter, _partial_suffix_len

pytestmark = pytest.mark.unit


def _run(chunks):
    """Feed each chunk in order, flush once, return the full event list."""
    sp = ThinkSplitter()
    events = []
    for c in chunks:
        events.extend(sp.feed(c))
    events.extend(sp.flush())
    return events


def _answer(events):
    return "".join(e["text"] for e in events if e["t"] == "answer")


def _thinking(events):
    return "".join(e["text"] for e in events if e["t"] == "thinking")


def test_no_tags_is_all_answer():
    events = _run(["Hello ", "world."])
    assert _answer(events) == "Hello world."
    assert _thinking(events) == ""
    assert all(e["t"] == "answer" for e in events)


def test_tags_within_a_single_chunk():
    events = _run(["ans<think>reason</think>more"])
    assert _answer(events) == "ansmore"
    assert _thinking(events) == "reason"


def test_open_tag_split_across_two_chunks():
    events = _run(["before <th", "ink>secret</think> after"])
    assert _answer(events) == "before  after"
    assert _thinking(events) == "secret"


def test_open_tag_split_across_three_chunks():
    events = _run(["<", "thi", "nk>x</think>y"])
    assert _answer(events) == "y"
    assert _thinking(events) == "x"


def test_close_tag_split_across_chunks():
    events = _run(["<think>ab", "</th", "ink>done"])
    assert _thinking(events) == "ab"
    assert _answer(events) == "done"


def test_unclosed_tag_flushes_as_thinking():
    events = _run(["visible <think>still thinking"])
    assert _answer(events) == "visible "
    assert _thinking(events) == "still thinking"


def test_partial_close_tag_at_stream_end_flushes_as_thinking():
    # An unfinished </think> at EOS is leftover literal thinking, never answer.
    events = _run(["<think>ab</thi"])
    assert _thinking(events) == "ab</thi"
    assert _answer(events) == ""


def test_char_by_char_adversarial():
    events = _run(list("a<think>bc</think>d"))
    assert _answer(events) == "ad"
    assert _thinking(events) == "bc"


def test_false_partial_is_not_a_tag():
    # "<thing>" shares a prefix with "<think>" but is literal answer text.
    events = _run(["hi <thi", "ng> there"])
    assert _answer(events) == "hi <thing> there"
    assert _thinking(events) == ""


def test_multiple_think_blocks():
    events = _run(["a<think>1</think>b<think>2</think>c"])
    assert _answer(events) == "abc"
    assert _thinking(events) == "12"


def test_text_after_close_tag_is_answer():
    events = _run(["<think>reason</think>the answer"])
    assert _thinking(events) == "reason"
    assert _answer(events) == "the answer"
    assert "<think>" not in _answer(events)
    assert "</think>" not in _answer(events)


def test_no_empty_text_events():
    events = _run(["<think></think>answer"])
    assert all(e["text"] for e in events)  # never emit empty-text events
    assert _answer(events) == "answer"
    assert _thinking(events) == ""


def test_empty_feeds_produce_nothing():
    sp = ThinkSplitter()
    assert sp.feed("") == []
    assert sp.flush() == []


def test_thinking_precedes_answer_in_order():
    events = _run(["<think>reason</think>", "the ", "answer"])
    kinds = [e["t"] for e in events]
    assert "thinking" in kinds and "answer" in kinds
    last_thinking = max(i for i, k in enumerate(kinds) if k == "thinking")
    assert kinds.index("answer") > last_thinking
    assert _thinking(events) == "reason"
    assert _answer(events) == "the answer"


@pytest.mark.parametrize(
    "buf,tag,expected",
    [
        ("hello<thi", "<think>", 4),      # "<thi" is a 4-char prefix of "<think>"
        ("hello", "<think>", 0),
        ("<", "<think>", 1),
        ("done</think", "</think>", 7),   # "</think" is a 7-char prefix of "</think>"
        ("x", "<think>", 0),
    ],
)
def test_partial_suffix_len(buf, tag, expected):
    assert _partial_suffix_len(buf, tag) == expected
