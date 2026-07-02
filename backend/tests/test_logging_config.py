"""Logging configuration: env-driven level, UTC timestamps, request-id injection.

Covers src.core.logging (formatters, filter, level resolution, stable file
name) and src.core.request_context (id generation and defaults).
"""

import logging
import os
import re
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from src.core.logging import (
    FILE_LOG_FORMAT,
    LOG_FILE_NAME,
    CustomFormatter,
    RequestIdFilter,
    configure_logger,
    resolve_log_level,
    utc_formatter,
)
from src.core.request_context import get_request_id, new_request_id, request_id_var

UTC_TS_PATTERN = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z"


@pytest.fixture
def restore_logging():
    """Re-apply the default logging configuration after level-mutating tests."""
    yield
    os.environ.pop("ERUDI_LOG_LEVEL", None)
    configure_logger()


def _make_record(
    level: int = logging.INFO,
    msg: str = "hello",
    pathname: str = "/Users/dev/Work/erudi/backend/src/core/api.py",
) -> logging.LogRecord:
    record = logging.LogRecord(
        name="erudi",
        level=level,
        pathname=pathname,
        lineno=42,
        msg=msg,
        args=(),
        exc_info=None,
    )
    record.request_id = "-"
    return record


# ---------------------------------------------------------------------------
# Level resolution (ERUDI_LOG_LEVEL)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_resolve_log_level_defaults_to_info():
    assert resolve_log_level(None) == logging.INFO
    assert resolve_log_level("") == logging.INFO


@pytest.mark.unit
def test_resolve_log_level_accepts_valid_names_case_insensitively():
    assert resolve_log_level("DEBUG") == logging.DEBUG
    assert resolve_log_level("warning") == logging.WARNING
    assert resolve_log_level(" error ") == logging.ERROR


@pytest.mark.unit
def test_resolve_log_level_invalid_value_falls_back_to_info():
    assert resolve_log_level("VERBOSE") == logging.INFO
    assert resolve_log_level("123abc") == logging.INFO


@pytest.mark.unit
def test_configure_logger_default_level_is_info(restore_logging):
    os.environ.pop("ERUDI_LOG_LEVEL", None)
    lg = configure_logger()
    assert lg.level == logging.INFO
    assert lg.handlers
    assert all(handler.level == logging.INFO for handler in lg.handlers)


@pytest.mark.unit
def test_configure_logger_respects_env_level(monkeypatch, restore_logging):
    monkeypatch.setenv("ERUDI_LOG_LEVEL", "DEBUG")
    lg = configure_logger()
    assert lg.level == logging.DEBUG
    assert all(handler.level == logging.DEBUG for handler in lg.handlers)


@pytest.mark.unit
def test_configure_logger_invalid_env_falls_back_to_info(monkeypatch, restore_logging):
    monkeypatch.setenv("ERUDI_LOG_LEVEL", "NOT_A_LEVEL")
    lg = configure_logger()
    assert lg.level == logging.INFO


@pytest.mark.unit
def test_configure_logger_is_idempotent(restore_logging):
    lg1 = configure_logger()
    handler_count = len(lg1.handlers)
    lg2 = configure_logger()
    assert lg2 is lg1
    assert len(lg2.handlers) == handler_count


# ---------------------------------------------------------------------------
# Formatters: UTC ISO-8601 with milliseconds, Z suffix
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_file_formatter_emits_utc_z_timestamp_with_ms():
    record = _make_record()
    record.created = 1751447732.0
    record.msecs = 123.0
    out = utc_formatter(FILE_LOG_FORMAT).format(record)
    expected = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(1751447732.0)) + ".123Z"
    assert expected in out


@pytest.mark.unit
def test_console_formatter_emits_utc_z_timestamp_with_ms():
    record = _make_record()
    out = CustomFormatter().format(record)
    assert re.search(UTC_TS_PATTERN, out)


@pytest.mark.unit
def test_console_formatter_does_not_mutate_record_pathname():
    record = _make_record(pathname="/Users/dev/Work/erudi/backend/src/core/api.py")
    original = record.pathname
    out = CustomFormatter().format(record)
    assert record.pathname == original
    assert "backend/src/core/api.py" in out


# ---------------------------------------------------------------------------
# Request-id filter and formatter tag
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_request_id_filter_injects_dash_outside_requests():
    record = logging.LogRecord("erudi", logging.INFO, __file__, 1, "msg", (), None)
    assert RequestIdFilter().filter(record) is True
    assert record.request_id == "-"


@pytest.mark.unit
def test_request_id_filter_injects_current_request_id():
    token = request_id_var.set("be-cafe1234")
    try:
        record = logging.LogRecord("erudi", logging.INFO, __file__, 1, "msg", (), None)
        RequestIdFilter().filter(record)
        assert record.request_id == "be-cafe1234"
    finally:
        request_id_var.reset(token)


@pytest.mark.unit
def test_both_formatters_include_request_id_tag():
    record = _make_record()
    record.request_id = "be-12345678"
    assert "[be-12345678]" in CustomFormatter().format(record)
    assert "[be-12345678]" in utc_formatter(FILE_LOG_FORMAT).format(record)


# ---------------------------------------------------------------------------
# File handler: stable name + rotation preserved
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_log_file_name_is_stable_with_rotation(restore_logging):
    lg = configure_logger()
    file_handlers = [h for h in lg.handlers if isinstance(h, RotatingFileHandler)]
    assert len(file_handlers) == 1
    handler = file_handlers[0]
    assert Path(handler.baseFilename).name == LOG_FILE_NAME == "backend.log"
    assert handler.maxBytes == 10 * 1024 * 1024
    assert handler.backupCount == 10


# ---------------------------------------------------------------------------
# Third-party silences
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_noisy_third_party_loggers_are_silenced():
    for name in ("httpx", "httpcore", "huggingface_hub", "uvicorn.access"):
        assert logging.getLogger(name).level >= logging.WARNING


# ---------------------------------------------------------------------------
# Request-context helpers
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_new_request_id_format_and_uniqueness():
    ids = {new_request_id() for _ in range(100)}
    assert len(ids) == 100
    assert all(re.fullmatch(r"be-[0-9a-f]{8}", rid) for rid in ids)


@pytest.mark.unit
def test_get_request_id_defaults_to_dash_outside_requests():
    assert get_request_id() == "-"
