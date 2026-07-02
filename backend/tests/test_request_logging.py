"""Request logging middleware: id propagation, access log, 500 fallback, streaming.

Uses a minimal FastAPI app (no lifespan, no DB) so the middleware and the
exception handlers are exercised in isolation, mirroring the conftest
TestClient pattern (raise_server_exceptions=False).
"""

import logging
import re

import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from src.core.api import RequestLoggingMiddleware, add_exception_handlers
from src.core.request_context import get_request_id

GENERATED_ID_PATTERN = r"be-[0-9a-f]{8}"


def _build_app() -> FastAPI:
    app = FastAPI()
    add_exception_handlers(app)
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/ping")
    async def ping():
        return {"request_id": get_request_id()}

    @app.get("/erudi/health")
    async def health():
        return {"status": "ok"}

    @app.get("/erudi/jobs/1/status")
    async def job_status():
        return {"state": "running"}

    @app.get("/boom")
    async def boom():
        raise RuntimeError("intentional test crash")

    @app.get("/stream")
    async def stream():
        async def gen():
            for i in range(3):
                yield f"chunk-{i}\n"

        return StreamingResponse(gen(), media_type="text/plain")

    return app


@pytest.fixture
def logging_client():
    with TestClient(_build_app(), raise_server_exceptions=False) as test_client:
        yield test_client


def _http_records(caplog):
    return [rec for rec in caplog.records if rec.getMessage().startswith("HTTP ")]


# ---------------------------------------------------------------------------
# X-Request-ID propagation
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_provided_request_id_is_echoed(logging_client):
    response = logging_client.get("/ping", headers={"X-Request-ID": "test-rid-42"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-rid-42"
    # The contextvar is visible from inside the endpoint.
    assert response.json()["request_id"] == "test-rid-42"


@pytest.mark.unit
def test_request_id_header_lookup_is_case_insensitive(logging_client):
    response = logging_client.get("/ping", headers={"x-ReQuEsT-iD": "mixed-case-rid"})
    assert response.headers["X-Request-ID"] == "mixed-case-rid"


@pytest.mark.unit
def test_request_id_generated_when_absent(logging_client):
    response = logging_client.get("/ping")
    rid = response.headers.get("X-Request-ID")
    assert rid is not None
    assert re.fullmatch(GENERATED_ID_PATTERN, rid)
    assert response.json()["request_id"] == rid


# ---------------------------------------------------------------------------
# Access log line
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_access_log_has_method_path_status_duration_and_id(logging_client, caplog):
    with caplog.at_level(logging.INFO, logger="erudi"):
        logging_client.get("/ping", headers={"X-Request-ID": "rid-log-test"})
    records = _http_records(caplog)
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.INFO
    message = record.getMessage()
    assert "HTTP GET /ping -> 200 in " in message
    assert message.rstrip().endswith("ms")
    assert record.request_id == "rid-log-test"


@pytest.mark.unit
def test_polling_paths_log_at_debug(logging_client, caplog):
    with caplog.at_level(logging.DEBUG, logger="erudi"):
        logging_client.get("/erudi/health")
        logging_client.get("/erudi/jobs/1/status")
    records = _http_records(caplog)
    assert len(records) == 2
    assert all(rec.levelno == logging.DEBUG for rec in records)


@pytest.mark.unit
def test_polling_paths_are_silent_at_info(logging_client, caplog):
    with caplog.at_level(logging.INFO, logger="erudi"):
        logging_client.get("/erudi/health")
    assert _http_records(caplog) == []


# ---------------------------------------------------------------------------
# Unhandled exception fallback
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_unhandled_exception_returns_structured_500(logging_client, caplog):
    with caplog.at_level(logging.INFO, logger="erudi"):
        response = logging_client.get("/boom", headers={"X-Request-ID": "rid-boom"})
    assert response.status_code == 500
    body = response.json()
    assert body["success"] is False
    assert body["error"]["type"] == "INTERNAL_SERVER_ERROR"
    assert "message" in body["error"]
    # The fallback handler must echo the id itself (its response bypasses the
    # request-logging middleware's send wrapper).
    assert response.headers.get("X-Request-ID") == "rid-boom"

    error_records = [rec for rec in caplog.records if rec.levelno == logging.ERROR]
    assert error_records
    assert any(rec.request_id == "rid-boom" for rec in error_records)
    assert any(rec.exc_info for rec in error_records)  # traceback captured


# ---------------------------------------------------------------------------
# Streaming: pass-through, unbuffered, single log line
# ---------------------------------------------------------------------------

@pytest.mark.unit
async def test_streaming_chunks_pass_through_unbuffered():
    """Raw ASGI probe: each body message must be forwarded as-is, one send per
    chunk, never coalesced or buffered by the middleware."""
    chunks = [b"first", b"second", b"third"]

    async def raw_app(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        for i, chunk in enumerate(chunks):
            await send(
                {
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": i < len(chunks) - 1,
                }
            )

    sent = []

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    wrapped = RequestLoggingMiddleware(raw_app)
    scope = {"type": "http", "method": "GET", "path": "/stream", "headers": []}
    await wrapped(scope, receive, send)

    body_messages = [m for m in sent if m["type"] == "http.response.body"]
    assert [m["body"] for m in body_messages] == chunks
    assert [m.get("more_body", False) for m in body_messages] == [True, True, False]

    start_messages = [m for m in sent if m["type"] == "http.response.start"]
    assert len(start_messages) == 1
    header_names = [name.lower() for name, _ in start_messages[0]["headers"]]
    assert b"x-request-id" in header_names


@pytest.mark.unit
def test_streaming_endpoint_still_streams_full_body(logging_client):
    with logging_client.stream("GET", "/stream") as response:
        content = b"".join(response.iter_raw())
    assert content == b"chunk-0\nchunk-1\nchunk-2\n"


@pytest.mark.unit
def test_streaming_request_logs_exactly_once(logging_client, caplog):
    with caplog.at_level(logging.INFO, logger="erudi"):
        logging_client.get("/stream")
    records = [
        rec for rec in caplog.records if rec.getMessage().startswith("HTTP GET /stream")
    ]
    assert len(records) == 1
    assert "-> 200 in " in records[0].getMessage()


# ---------------------------------------------------------------------------
# Exception severity mapping (AppBaseException)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_client_error_exceptions_log_at_warning(caplog):
    from src.core.exceptions import ModelNotFoundException

    with caplog.at_level(logging.WARNING, logger="erudi"):
        ModelNotFoundException("ghost-model")  # constructing logs
    assert caplog.records
    assert all(rec.levelno == logging.WARNING for rec in caplog.records)


@pytest.mark.unit
def test_server_error_exceptions_log_at_error(caplog):
    from src.core.exceptions import EngineException

    with caplog.at_level(logging.WARNING, logger="erudi"):
        EngineException("engine died")
    assert caplog.records
    assert any(rec.levelno == logging.ERROR for rec in caplog.records)


@pytest.mark.unit
def test_options_preflight_logs_at_debug(logging_client, caplog):
    with caplog.at_level(logging.DEBUG, logger="erudi"):
        logging_client.options("/ping")
    records = _http_records(caplog)
    assert len(records) == 1
    assert records[0].levelno == logging.DEBUG
    assert "HTTP OPTIONS /ping" in records[0].getMessage()
