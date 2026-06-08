"""Guard the PyInstaller specs against an mlx-vlm/mlx_lm regression.

The MLX bundle must collect `mlx_vlm` and hidden-import the mlx-vlm runner +
server, with no `mlx_lm.server` / `_mlx_server_runner` left behind. These
specs are only exercised at build time, so this text guard is the only
automated check that the swap reached them.
"""
import pathlib

import pytest

_BACKEND = pathlib.Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    path = _BACKEND / name
    if not path.exists():
        # Some specs (e.g. the CPU variant) are gitignored / build-time only.
        pytest.skip(f"{name} not present in this checkout")
    return path.read_text(encoding="utf-8")


@pytest.mark.unit
def test_mac_silicon_spec_collects_mlx_vlm():
    spec = _read("backend-mac-silicon.spec")
    assert 'collect_all("mlx_vlm")' in spec
    assert 'collect_all("mlx_lm")' not in spec
    assert "src.engines._mlx_vlm_server_runner" in spec
    assert '"mlx_vlm.server"' in spec
    assert "_mlx_server_runner" not in spec
    assert '"mlx_lm.server"' not in spec


@pytest.mark.unit
def test_mac_silicon_spec_excludes_unused_heavy_deps():
    # Lazy mlx-vlm deps that the inference / vision-input path never imports.
    spec = _read("backend-mac-silicon.spec")
    assert '"cv2"' in spec
    assert '"mlx_audio"' in spec


@pytest.mark.unit
def test_backend_spec_targets_mlx_vlm_not_mlx_lm():
    spec = _read("backend.spec")
    assert "mlx_vlm" in spec
    assert "mlx_lm" not in spec


@pytest.mark.unit
def test_cpu_spec_excludes_mlx_vlm():
    spec = _read("backend-cpu.spec")
    assert "mlx_vlm" in spec
    assert "mlx_lm" not in spec
