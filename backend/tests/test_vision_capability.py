"""Tests for static vision-capability detection (issue #133, bug #4).

``unit``: the pure ``config_declares_vision`` helper that decides, from a
HuggingFace ``config.json`` dict, whether a model accepts image input. It backs
``MLX_Engine.model_supports_vision``; the llama.cpp side keys off an ``mmproj``
file instead and is covered in the engine tests.
"""
from __future__ import annotations

import pytest

from src.engines.vision_capability import config_declares_vision


@pytest.mark.unit
def test_vision_config_subdict_is_vision():
    cfg = {
        "model_type": "gemma3",
        "architectures": ["Gemma3ForConditionalGeneration"],
        "vision_config": {"hidden_size": 1152},
    }
    assert config_declares_vision(cfg) is True


@pytest.mark.unit
def test_vision_tower_marker_is_vision():
    assert config_declares_vision({"mm_vision_tower": "openai/clip-vit"}) is True


@pytest.mark.unit
def test_image_token_index_is_vision():
    assert config_declares_vision({"model_type": "qwen2_vl", "image_token_index": 151655}) is True


@pytest.mark.unit
def test_explicit_vision_architecture_is_vision():
    assert config_declares_vision({"architectures": ["MllamaForConditionalGeneration"]}) is True
    assert config_declares_vision({"architectures": ["LlavaForConditionalGeneration"]}) is True


@pytest.mark.unit
def test_plain_text_model_is_not_vision():
    cfg = {"model_type": "qwen2", "architectures": ["Qwen2ForCausalLM"]}
    assert config_declares_vision(cfg) is False


@pytest.mark.unit
def test_seq2seq_text_conditionalgeneration_is_not_vision():
    # T5 et co. sont ForConditionalGeneration mais texte pur — ne doit pas matcher.
    cfg = {"model_type": "t5", "architectures": ["T5ForConditionalGeneration"]}
    assert config_declares_vision(cfg) is False


@pytest.mark.unit
def test_non_dict_or_empty_is_not_vision():
    assert config_declares_vision({}) is False
    assert config_declares_vision(None) is False
    assert config_declares_vision("nope") is False
