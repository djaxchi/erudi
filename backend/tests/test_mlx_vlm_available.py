"""mlx-vlm availability guard (Apple Silicon only).

After the swap the MLX engine spawns ``mlx_vlm.server`` instead of
``mlx_lm.server``. This pins that the server entrypoint and the convert
helper are importable in the installed surface. ``mlx-vlm`` is a macOS-only
pin, so the file is excluded from the Linux CI via ``mlx_only`` and also
guarded by ``is_mlx_platform`` for non-Apple local runs.
"""
import pytest

from tests._helpers import is_mlx_platform

pytestmark = [
    pytest.mark.mlx_only,
    pytest.mark.skipif(not is_mlx_platform(), reason="mlx-vlm is macOS/Apple-Silicon only"),
]


def test_mlx_vlm_server_app_importable():
    from mlx_vlm.server import app  # noqa: F401
    from mlx_vlm.server.cli import main

    assert callable(main)


def test_mlx_vlm_convert_importable():
    from mlx_vlm import convert

    assert callable(convert)
