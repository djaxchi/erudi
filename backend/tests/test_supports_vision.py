"""Tests for static vision (image-input) capability detection (#133, bug #4).

- ``unit``: the ``detect_supports_vision`` repository helper (engine verdict,
  graceful None) and the llama.cpp engine hook (mmproj presence).
- ``mlx_only``: the MLX engine hook reads ``config.json`` (Apple Silicon only).
"""
from __future__ import annotations

import json

import pytest

from src.domains.llms.repository import detect_supports_vision
from src.engines.cpu_engine import CPU_Engine
from tests._helpers import is_mlx_platform


# ---------------- unit: detect_supports_vision helper ----------------


class _VisionEngine:
    @staticmethod
    def model_supports_vision(local_path):
        return True


class _TextEngine:
    @staticmethod
    def model_supports_vision(local_path):
        return False


class _BoomEngine:
    @staticmethod
    def model_supports_vision(local_path):
        raise RuntimeError("boom")


@pytest.mark.unit
def test_detect_returns_engine_verdict_true(monkeypatch):
    monkeypatch.setattr("src.core.config.LLM_Engine", _VisionEngine)
    assert detect_supports_vision("/m/path") is True


@pytest.mark.unit
def test_detect_returns_engine_verdict_false(monkeypatch):
    monkeypatch.setattr("src.core.config.LLM_Engine", _TextEngine)
    assert detect_supports_vision("/m/path") is False


@pytest.mark.unit
def test_detect_none_when_engine_unset(monkeypatch):
    monkeypatch.setattr("src.core.config.LLM_Engine", None)
    assert detect_supports_vision("/m/path") is None


@pytest.mark.unit
def test_detect_none_when_path_empty(monkeypatch):
    monkeypatch.setattr("src.core.config.LLM_Engine", _VisionEngine)
    assert detect_supports_vision("") is None


@pytest.mark.unit
def test_detect_none_on_engine_error(monkeypatch):
    monkeypatch.setattr("src.core.config.LLM_Engine", _BoomEngine)
    assert detect_supports_vision("/m/path") is None


# ---------------- unit: llama.cpp engine hook (mmproj) ----------------


@pytest.mark.unit
def test_llamacpp_vision_true_with_mmproj(tmp_path):
    (tmp_path / "model.q4_k_m.gguf").write_bytes(b"x")
    (tmp_path / "mmproj-model.gguf").write_bytes(b"y")
    assert CPU_Engine.model_supports_vision(tmp_path) is True


@pytest.mark.unit
def test_llamacpp_vision_false_without_mmproj(tmp_path):
    (tmp_path / "model.q4_k_m.gguf").write_bytes(b"x")
    assert CPU_Engine.model_supports_vision(tmp_path) is False


@pytest.mark.unit
def test_llamacpp_vision_none_when_no_gguf(tmp_path):
    # _select_gguf raises (no artifact) -> undeterminable -> None (permissive).
    assert CPU_Engine.model_supports_vision(tmp_path) is None


# ---------------- mlx_only: MLX engine hook (config.json) ----------------


# ---------------- unit: LLMResponse computed field ----------------


@pytest.mark.unit
def test_llm_response_computes_vision_for_local(monkeypatch):
    monkeypatch.setattr("src.core.config.LLM_Engine", _VisionEngine)
    from src.domains.llms.schemas import LLMResponse

    resp = LLMResponse(id=1, name="VLM", local=1, link="/m/path")
    assert resp.supports_vision is True
    assert resp.model_dump()["supports_vision"] is True


@pytest.mark.unit
def test_llm_response_vision_none_for_remote(monkeypatch):
    # Remote rows are not yet on disk -> capability is unknown (None), not False.
    monkeypatch.setattr("src.core.config.LLM_Engine", _VisionEngine)
    from src.domains.llms.schemas import LLMResponse

    resp = LLMResponse(id=1, name="VLM", local=0, link="Org/Repo")
    assert resp.supports_vision is None


@pytest.mark.unit
def test_llm_response_vision_false_for_text_model(monkeypatch):
    monkeypatch.setattr("src.core.config.LLM_Engine", _TextEngine)
    from src.domains.llms.schemas import LLMResponse

    resp = LLMResponse(id=1, name="Text", local=1, link="/m/path")
    assert resp.supports_vision is False


# ---------------- mlx_only: MLX engine hook (config.json) ----------------


@pytest.mark.mlx_only
@pytest.mark.skipif(not is_mlx_platform(), reason="MLX engine import requires Apple Silicon")
def test_mlx_vision_true_from_config(tmp_path):
    from src.engines.mlx_engine import MLX_Engine

    (tmp_path / "config.json").write_text(
        json.dumps({"vision_config": {}, "architectures": ["Gemma3ForConditionalGeneration"]})
    )
    assert MLX_Engine.model_supports_vision(tmp_path) is True


@pytest.mark.mlx_only
@pytest.mark.skipif(not is_mlx_platform(), reason="MLX engine import requires Apple Silicon")
def test_mlx_vision_false_for_text(tmp_path):
    from src.engines.mlx_engine import MLX_Engine

    (tmp_path / "config.json").write_text(json.dumps({"architectures": ["Qwen2ForCausalLM"]}))
    assert MLX_Engine.model_supports_vision(tmp_path) is False
