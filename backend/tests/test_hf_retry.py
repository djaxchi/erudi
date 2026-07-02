"""get_hf_api() returns a client that survives HF anonymous rate limiting (#108
follow-up). The build-time catalog snapshot generation fires hundreds of anonymous
metadata calls in a burst; a 429 must be retried (with backoff), not abort the build
or be swallowed as 'no result'. These are offline unit tests — the HfApi base
methods are stubbed."""
from types import SimpleNamespace

import httpx
import pytest
from huggingface_hub.errors import HfHubHTTPError

from src.core import config as cfg


def _http_error(status: int) -> HfHubHTTPError:
    resp = httpx.Response(status, request=httpx.Request("GET", "https://huggingface.co/api/models"))
    return HfHubHTTPError("boom", response=resp)


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    # Don't actually wait through the backoff in tests.
    monkeypatch.setattr(cfg.time, "sleep", lambda *a, **k: None)


class TestRetryingHfApi:
    def test_list_models_retries_on_429_then_succeeds(self, monkeypatch):
        calls = {"n": 0}

        def fake(self, *a, **k):
            calls["n"] += 1
            if calls["n"] < 3:
                raise _http_error(429)
            return iter([SimpleNamespace(id="org/model")])

        monkeypatch.setattr(cfg.HfApi, "list_models", fake)
        api = cfg._RetryingHfApi(token=None)
        out = api.list_models(filter="mlx", search="x", limit=5)
        assert calls["n"] == 3
        assert [m.id for m in out] == ["org/model"]   # materialized, not a generator

    def test_model_info_retries_on_429_then_succeeds(self, monkeypatch):
        calls = {"n": 0}

        def fake(self, *a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise _http_error(429)
            return SimpleNamespace(id="org/model")

        monkeypatch.setattr(cfg.HfApi, "model_info", fake)
        api = cfg._RetryingHfApi(token=None)
        assert api.model_info("org/model").id == "org/model"
        assert calls["n"] == 2

    def test_non_429_propagates_without_retry(self, monkeypatch):
        calls = {"n": 0}

        def fake(self, *a, **k):
            calls["n"] += 1
            raise _http_error(404)

        monkeypatch.setattr(cfg.HfApi, "list_models", fake)
        api = cfg._RetryingHfApi(token=None)
        with pytest.raises(HfHubHTTPError):
            api.list_models(filter="mlx", limit=5)
        assert calls["n"] == 1   # a 404 is a real answer, not retried

    def test_persistent_429_eventually_raises(self, monkeypatch):
        def fake(self, *a, **k):
            raise _http_error(429)

        monkeypatch.setattr(cfg.HfApi, "model_info", fake)
        api = cfg._RetryingHfApi(token=None)
        with pytest.raises(HfHubHTTPError):
            api.model_info("org/model")
