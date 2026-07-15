"""Bounded offline probes (issue #109 P1/P2).

- ``is_online()`` must issue a single ``requests.head`` with a hard, bounded
  (connect, read) timeout, return True on any completed round trip, and False
  on any exception -- never hang. No real network: ``requests.head`` is mocked.
- An offline model download must surface the friendly ``OFFLINE_DOWNLOAD_MESSAGE``
  instead of the raw hf_hub "Cannot reach https://..." string, mirroring the e5
  embedding-download offline path.
"""
import pytest
import requests

from src.core.exceptions import HuggingFaceAPIException
from src.database.seed import is_online
from src.domains.llms.services import (
    OFFLINE_DOWNLOAD_MESSAGE,
    _is_offline_download_error,
)

pytestmark = pytest.mark.unit


class TestIsOnline:
    def test_true_on_completed_head_with_bounded_timeout(self, monkeypatch):
        seen = {}

        def fake_head(url, **kwargs):
            seen["url"] = url
            seen["kwargs"] = kwargs
            return object()  # any completed response counts as reachable

        monkeypatch.setattr(requests, "head", fake_head)

        assert is_online() is True
        assert seen["url"] == "https://huggingface.co"
        # The whole point of the fix: a real, bounded (connect, read) timeout.
        assert seen["kwargs"]["timeout"] == (3, 3)
        assert seen["kwargs"]["allow_redirects"] is True

    def test_true_even_on_error_status(self, monkeypatch):
        # We only assert reachability, not a 2xx: a returned 503 still means the
        # network round trip completed, so is_online is True (no raise_for_status).
        resp = requests.models.Response()
        resp.status_code = 503
        monkeypatch.setattr(requests, "head", lambda url, **kw: resp)
        assert is_online() is True

    def test_false_on_connection_error(self, monkeypatch):
        def boom(url, **kwargs):
            raise requests.exceptions.ConnectionError("getaddrinfo failed")

        monkeypatch.setattr(requests, "head", boom)
        assert is_online() is False

    def test_false_on_read_timeout(self, monkeypatch):
        def boom(url, **kwargs):
            raise requests.exceptions.ReadTimeout("timed out")

        monkeypatch.setattr(requests, "head", boom)
        assert is_online() is False

    def test_false_on_connect_timeout(self, monkeypatch):
        def boom(url, **kwargs):
            raise requests.exceptions.ConnectTimeout("connect timed out")

        monkeypatch.setattr(requests, "head", boom)
        assert is_online() is False


class TestOfflineDownloadErrorMapping:
    def test_requests_connection_error_is_offline(self):
        exc = requests.exceptions.ConnectionError("Max retries exceeded with url")
        assert _is_offline_download_error(exc) is True

    def test_hf_cannot_reach_message_is_offline(self):
        exc = Exception(
            "Cannot reach https://huggingface.co: (ConnectionError) network down"
        )
        assert _is_offline_download_error(exc) is True

    def test_chained_connection_error_is_offline(self):
        # hf_hub/transformers re-wrap the original error; the chain must be walked.
        outer = None
        try:
            try:
                raise requests.exceptions.ConnectionError("boom")
            except Exception as inner:
                raise RuntimeError("download failed") from inner
        except RuntimeError as e:
            outer = e
        assert _is_offline_download_error(outer) is True

    def test_generic_errors_are_not_offline(self):
        assert _is_offline_download_error(ValueError("no space left on device")) is False
        assert _is_offline_download_error(Exception("403 Client Error: Forbidden")) is False

    def test_offline_message_is_ascii_and_friendly(self):
        # ASCII-safe (no em dash) so it is log-safe on cp1252 consoles.
        OFFLINE_DOWNLOAD_MESSAGE.encode("ascii")
        assert "offline" in OFFLINE_DOWNLOAD_MESSAGE.lower()

    def test_mapped_exception_carries_friendly_message_verbatim(self):
        # The download except-block raises this; endpoints store str(e) as the
        # job's error_message, so str() must be the friendly text (no support
        # suffix, which AppBaseException only appends to .message).
        exc = HuggingFaceAPIException(OFFLINE_DOWNLOAD_MESSAGE, trace="raw hub error")
        assert str(exc) == OFFLINE_DOWNLOAD_MESSAGE
