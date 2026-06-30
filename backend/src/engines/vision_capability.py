"""Static vision-capability detection from a HuggingFace ``config.json`` (#133).

Mirror of ``tool_capability`` but for image input: given a model's parsed
``config.json``, decide whether it is a vision/multimodal model. Used by
``MLX_Engine.model_supports_vision``; the llama.cpp engines key off the presence
of an ``mmproj-*.gguf`` projector instead (see ``BaseLlamaCppEngine``).
"""
from __future__ import annotations

# Config fields a multimodal checkpoint carries. ``vision_config`` is the
# strongest, near-universal signal (Gemma3, Qwen-VL, Llava, Mllama, Phi-vision…);
# the others cover Llava-style and token-index variants.
_VISION_CONFIG_KEYS = (
    "vision_config",
    "vision_tower",
    "mm_vision_tower",
    "image_token_index",
    "image_token_id",
)

# Architecture-name fragments that unambiguously denote a vision model. Kept
# explicit to known VLM families — deliberately NOT "conditionalgeneration",
# which seq2seq text models (T5) also use, nor a bare "vl" (too many false hits).
_VISION_ARCH_MARKERS = (
    "vision",
    "llava",
    "mllama",
    "idefics",
    "paligemma",
    "internvl",
    "smolvlm",
)


def config_declares_vision(config) -> bool:
    """True if the model ``config.json`` dict denotes an image-input model."""
    if not isinstance(config, dict):
        return False
    if any(key in config for key in _VISION_CONFIG_KEYS):
        return True
    archs = config.get("architectures") or []
    low = " ".join(a.lower() for a in archs if isinstance(a, str))
    return any(marker in low for marker in _VISION_ARCH_MARKERS)
