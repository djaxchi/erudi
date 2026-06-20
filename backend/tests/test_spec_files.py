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
    # mlx_lm IS collected — not as a server, but because mlx-vlm's text-only
    # path imports the per-architecture model module (mlx_lm.models.<arch>) by
    # name at runtime (bug 5). The swap guard is that the SERVER stays mlx-vlm.
    assert 'collect_all("mlx_lm")' in spec
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
def test_mac_silicon_spec_bundles_py3langid_data():
    # The langid model (model.plzma) is package data loaded at runtime by
    # src/agents/language.py; without collecting it the systematic KB path
    # dies with FileNotFoundError (packaging bug 6).
    spec = _read("backend-mac-silicon.spec")
    assert 'collect_data_files("py3langid")' in spec


@pytest.mark.unit
def test_backend_spec_targets_mlx_vlm_not_mlx_lm():
    spec = _read("backend.spec")
    assert "mlx_vlm" in spec
    assert "mlx_lm" not in spec


@pytest.mark.unit
def test_all_specs_bundle_py3langid_data():
    # The systematic KB path (detect_language) is shared across platforms, so
    # every spec must collect py3langid's model data (packaging bug 6).
    for name in ("backend-mac-silicon.spec", "backend.spec"):
        spec = _read(name)
        assert 'collect_data_files("py3langid")' in spec, name


@pytest.mark.unit
def test_all_specs_collect_pgserver_binaries():
    # pgserver's embedded postgres binaries must be collected on every platform,
    # else the frozen backend dies at startup (packaging bug 1).
    for name in ("backend-mac-silicon.spec", "backend.spec"):
        spec = _read(name)
        assert 'collect_all("pgserver")' in spec, name


@pytest.mark.unit
def test_cpu_spec_excludes_mlx_vlm():
    spec = _read("backend-cpu.spec")
    assert "mlx_vlm" in spec
    assert "mlx_lm" not in spec


@pytest.mark.unit
def test_backend_spec_bundles_variant_llama_server():
    # The Windows llama-server bundle must follow the build variant so the cpu
    # spec ships artifacts/llama-cpp/cpu/bin and the (default) cuda spec ships
    # .../cuda/bin — NOT a hardcoded cuda-only path. Both flavours are compiled
    # in CI from the llama.cpp submodule before PyInstaller runs (see release.yml).
    spec = _read("backend.spec")
    assert "ERUDI_BUILD_VARIANT" in spec
    assert "_llama_flavour" in spec
    # the previous hardcoded cuda-only data path must be gone
    assert '"llama-cpp" / "cuda" / "bin"' not in spec
