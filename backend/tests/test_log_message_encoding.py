"""Log messages must stay ASCII-only.

The Windows console and the log file the app writes are not read back as
UTF-8, so a `->` written as an arrow lands in `%LOCALAPPDATA%\\erudi\\logs\\
backend.log` as mojibake (`â†’`), which is what #149/#168 were about. CLAUDE.md
states the rule; nothing enforced it, and nine call sites had drifted back by
the 2.0.0 draft. This test is the enforcement.

Comments and docstrings are deliberately not covered: Python reads source as
UTF-8 whatever the locale, so they are safe and often clearer with real
punctuation. Only what reaches a log line is checked.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"

LOG_METHODS = {"info", "warning", "error", "debug", "exception", "critical"}


def _is_logger_call(node: ast.Call) -> bool:
    """True for `logger.info(...)` and friends, however `logger` was obtained."""
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr not in LOG_METHODS:
        return False
    target = func.value
    while isinstance(target, ast.Attribute):
        target = target.value
    return isinstance(target, ast.Name) and target.id.endswith("logger")


def _string_parts(node: ast.AST):
    """Every literal string inside a call, f-string pieces included."""
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            yield child


def _offenders():
    found = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _is_logger_call(node):
                continue
            for const in _string_parts(node):
                if not const.value.isascii():
                    bad = sorted({c for c in const.value if not c.isascii()})
                    found.append(
                        f"{path.relative_to(SRC.parent)}:{const.lineno} "
                        f"contains {bad} in a log message"
                    )
    return found


@pytest.mark.unit
def test_log_messages_are_ascii_only():
    offenders = _offenders()
    assert not offenders, "Non-ASCII in log messages:\n  " + "\n  ".join(offenders)


@pytest.mark.unit
def test_the_check_actually_looks_at_something():
    """Guard the guard: a walker that matches nothing would pass silently."""
    tree = ast.parse("logger.info(f'a {x} b')\nlogger.warning('c')\nprint('d')\n")
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and _is_logger_call(n)]
    assert len(calls) == 2
    assert {c.value for c in _string_parts(calls[0])} == {"a ", " b"}
