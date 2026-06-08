"""Guard against mlx_lm.server residue after the mlx-vlm swap.

The MLX engine no longer spawns `mlx_lm.server`: the old runner module is gone
and no engine module imports `mlx_lm` functionally. Comparative comments (e.g.
"no mlx_lm.server EOS-flush drop") are intentional and allowed — this guard
only polices real imports, the deleted runner, and the dropped sentinel.
"""
import ast
import importlib.util
import pathlib

import pytest

_ENGINES = pathlib.Path(__file__).resolve().parents[1] / "src" / "engines"


@pytest.mark.unit
def test_old_runner_module_removed():
    assert importlib.util.find_spec("src.engines._mlx_server_runner") is None


@pytest.mark.unit
def test_no_functional_mlx_lm_imports_in_engines():
    offenders: list[str] = []
    for py in sorted(_ENGINES.glob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("mlx_lm"):
                offenders.append(f"{py.name}: from {node.module} import ...")
            elif isinstance(node, ast.Import):
                offenders += [
                    f"{py.name}: import {n.name}"
                    for n in node.names
                    if n.name == "mlx_lm" or n.name.startswith("mlx_lm.")
                ]
            elif (
                isinstance(node, ast.Call)
                and getattr(node.func, "attr", "") == "import_module"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and str(node.args[0].value).startswith("mlx_lm")
            ):
                offenders.append(f"{py.name}: import_module({node.args[0].value!r})")
    assert not offenders, offenders


@pytest.mark.unit
def test_mlx_engine_does_not_use_default_model_sentinel():
    from src.engines.mlx_engine import MLX_Engine

    value = MLX_Engine._payload_model_value({"alias": "a", "model_path": "/m"})
    assert value == "/m"
    assert value != "default_model"
