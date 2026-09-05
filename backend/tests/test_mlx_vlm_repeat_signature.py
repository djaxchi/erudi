"""Regression guard for #378: Qwen2.5-VL images on the packaged mac build.

The 2.0.0 macOS build resolved ``mlx==0.32.2`` (transitively, ``mlx`` was not
pinned) next to ``mlx-vlm==0.6.13``. In that mlx the nanobind signature of
``mx.repeat`` is strict (``repeats: int``), and 0.6.13's Qwen2.5-VL vision
tower passed an ``mx.array`` for it::

    mlx_vlm/models/qwen2_5_vl/vision.py:367
        cu_seqlens.append(mx.repeat(seq_len, grid_thw[i, 0]))
    TypeError: repeat(): incompatible function arguments.

Every image sent to any Qwen2.5-VL (and Qwen2-VL, same call) model raised.
The dev venv carried an older mlx where the array form was still accepted, so
no local run showed it. Upstream fixed the call in mlx-vlm 0.6.17
(``int(grid_thw[i, 0])``); the fix pins ``mlx-vlm==0.6.17`` and ``mlx==0.32.2``
in ``requirements/meta/mac-silicon-specs.txt`` so dev and prod converge.

This file pins the three facts the fix rests on: the installed mlx-vlm is at
least 0.6.17, its Qwen2.5-VL / Qwen2-VL vision towers carry the ``int()``
cast, and ``mx.repeat`` accepts the int form the fixed code uses. Imports of
``mlx`` / ``mlx_vlm`` stay inside the tests so the module collects on Linux CI
(the ``mlx_only`` marker deselects it there).
"""

from __future__ import annotations

import importlib.metadata
from pathlib import Path

import pytest
from packaging.version import Version

from tests._helpers import is_mlx_platform

pytestmark = [
    pytest.mark.mlx_only,
    pytest.mark.skipif(not is_mlx_platform(), reason="mlx-vlm is macOS/Apple-Silicon only"),
]

# First mlx-vlm release whose Qwen2.5-VL vision tower casts the repeat count
# to int (0.6.14-0.6.16 declare mlx>=0.32.0 but still pass the array).
_MIN_MLX_VLM = Version("0.6.17")

# The exact form of the upstream fix at qwen2_5_vl/vision.py:367 (and the
# sibling qwen2_vl tower); the 0.6.13 line is `mx.repeat(seq_len, grid_thw[i, 0])`.
_FIXED_CALL = "int(grid_thw[i, 0])"
_BROKEN_CALL = "mx.repeat(seq_len, grid_thw[i, 0])"

_VISION_TOWERS = ("qwen2_5_vl", "qwen2_vl")


def _vision_source(family: str) -> str:
    import mlx_vlm

    path = Path(mlx_vlm.__file__).resolve().parent / "models" / family / "vision.py"
    assert path.is_file(), f"{family} vision tower missing from installed mlx-vlm: {path}"
    return path.read_text(encoding="utf-8")


def test_installed_mlx_vlm_is_at_least_0_6_17():
    installed = Version(importlib.metadata.version("mlx-vlm"))
    assert installed >= _MIN_MLX_VLM, (
        f"mlx-vlm {installed} < {_MIN_MLX_VLM}: its Qwen2.5-VL vision tower passes an "
        f"mx.array to mx.repeat, which mlx>=0.32.2 rejects (#378)"
    )


def test_installed_mlx_satisfies_the_0_6_17_floor():
    # 0.6.17 declares mlx>=0.32.0; the specs pin the exact version the release
    # build resolved so the venv reproduces the packaged combination.
    installed = Version(importlib.metadata.version("mlx"))
    assert installed >= Version("0.32.2"), (
        f"mlx {installed} is older than the pinned 0.32.2: the dev venv would not "
        f"reproduce the packaged build's strict mx.repeat signature (#378)"
    )


@pytest.mark.parametrize("family", _VISION_TOWERS)
def test_vision_tower_casts_repeat_count_to_int(family: str):
    source = _vision_source(family)
    assert _BROKEN_CALL not in source, (
        f"{family}/vision.py still calls {_BROKEN_CALL!r}: images raise TypeError on "
        f"mlx>=0.32.2 (#378)"
    )
    assert _FIXED_CALL in source, (
        f"{family}/vision.py no longer contains {_FIXED_CALL!r}; re-check the upstream "
        f"cu_seqlens computation against the strict mx.repeat signature"
    )


def test_mx_repeat_accepts_the_int_form_the_fixed_tower_uses():
    import mlx.core as mx

    # Shape of the fixed call: a 0-d seq_len repeated `t` (an int) times.
    grid_thw = mx.array([[1, 2, 2]])
    seq_len = grid_thw[0, 1] * grid_thw[0, 2]
    repeated = mx.repeat(seq_len, int(grid_thw[0, 0]))
    assert repeated.tolist() == [4]

    assert mx.repeat(mx.array([1, 2]), 2).tolist() == [1, 1, 2, 2]
