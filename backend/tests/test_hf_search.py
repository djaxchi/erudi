"""Live-HF search service + by-link download endpoint (#122 follow-up).

The search box queries HF directly, filtered to runnable chat/vision models in the
active engine format, and a chosen hit downloads by repo id without being persisted
into the curated catalog. HF is mocked — no network.
"""
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock

import pytest
from fastapi import status

from src.domains.llms import hf_search
from src.entities.Llm import Llm


def _hit(mid, downloads=1000, pipeline_tag="text-generation", tags=None, total=None):
    st = SimpleNamespace(total=total) if total else None
    return SimpleNamespace(id=mid, downloads=downloads, likes=3, gated=False,
                           pipeline_tag=pipeline_tag, tags=tags or [], safetensors=st)


class _Engine:
    FORMAT_TAG = "mlx"

    @staticmethod
    def is_runnable(link):
        return True


@pytest.mark.unit
class TestSearchHuggingface:
    def test_empty_query_returns_empty(self):
        assert hf_search.search_huggingface("") == []
        assert hf_search.search_huggingface("   ") == []

    def test_filters_non_llm_pipelines_and_floor(self, monkeypatch):
        monkeypatch.setattr(hf_search.config, "LLM_Engine", _Engine, raising=False)
        api = SimpleNamespace(list_models=lambda **k: [
            _hit("mlx-community/Qwen2.5-7B-Instruct-4bit", downloads=5000, total=7_600_000_000),
            _hit("org/whisper-tiny-mlx", pipeline_tag="automatic-speech-recognition"),  # drop
            _hit("org/pii-french-mlx", pipeline_tag="token-classification"),            # drop
            _hit("org/dead-repo-4bit", downloads=2),                                    # below floor
            _hit("mlx-community/Qwen2.5-VL-7B-Instruct-4bit", pipeline_tag="image-text-to-text"),
        ])
        monkeypatch.setattr(hf_search.config, "get_hf_api", lambda: api)

        res = hf_search.search_huggingface("qwen", limit=10)
        links = [r["link"] for r in res]
        assert "mlx-community/Qwen2.5-7B-Instruct-4bit" in links
        assert "mlx-community/Qwen2.5-VL-7B-Instruct-4bit" in links  # vision kept
        assert all("whisper" not in x and "pii" not in x and "dead" not in x for x in links)

    def test_result_shape_and_category(self, monkeypatch):
        monkeypatch.setattr(hf_search.config, "LLM_Engine", _Engine, raising=False)
        api = SimpleNamespace(list_models=lambda **k: [
            _hit("mlx-community/Qwen2.5-Coder-7B-Instruct-4bit", total=7_600_000_000),
        ])
        monkeypatch.setattr(hf_search.config, "get_hf_api", lambda: api)

        (r,) = hf_search.search_huggingface("coder", limit=5)
        assert r["category"] == "code"
        assert r["param_size"] == 7.6
        assert r["quantized"] is True
        assert r["link"].endswith("Qwen2.5-Coder-7B-Instruct-4bit")

    def test_search_failure_returns_empty(self, monkeypatch):
        monkeypatch.setattr(hf_search.config, "LLM_Engine", _Engine, raising=False)
        def boom(**k):
            raise RuntimeError("HF down")
        monkeypatch.setattr(hf_search.config, "get_hf_api",
                            lambda: SimpleNamespace(list_models=boom))
        assert hf_search.search_huggingface("qwen") == []


@pytest.mark.unit
class TestHFDownloadEndpoint:
    @patch("src.domains.llms.endpoints.download_llm")
    @patch("pathlib.Path.exists")
    def test_download_by_link_starts_job(self, mock_exists, mock_download, client, test_db_session):
        mock_exists.return_value = False
        mock_download.return_value = AsyncMock()

        before = test_db_session.query(Llm).count()
        resp = client.post("/erudi/llms/download/huggingface", json={
            "link": "mlx-community/Some-Model-4bit", "name": "Some Model",
            "param_size": 7.0, "quantized": True, "category": "general",
        })
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["remote_model_link"] == "mlx-community/Some-Model-4bit"
        # A local=2 placeholder was created (download target), distinct from the catalog.
        assert test_db_session.query(Llm).count() == before + 1

    def test_download_by_link_requires_link(self, client):
        resp = client.post("/erudi/llms/download/huggingface", json={"name": "x"})
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
