"""Catalog ↔ engine quant-mapping invariants (#95).

These guard the token-free-by-construction design: every catalogued base model
must resolve to a public quant in the active engine's format (MLX on Apple
Silicon, GGUF on CPU/CUDA), so a download never hits the gated first-party
safetensors. They are pure class-attribute checks — no network, CI-safe.
"""

import pytest

from src.database.seed import Database_Seeder
from src.engines.base_llama_cpp_engine import BaseLlamaCppEngine
from src.engines.cpu_engine import CPU_Engine
from src.engines.cuda_engine import CUDA_Engine
from src.engines.mlx_engine import MLX_Engine

CATALOG_LINKS = [m.link for m in Database_Seeder.DEFAULT_BASE_MODELS]


class TestGgufMappingSharedAcrossLlamaCppEngines:
    """The GGUF catalog lives once on BaseLlamaCppEngine; CPU and CUDA inherit it."""

    def test_uses_gguf_is_inherited_true(self):
        # Was CUDA-only, leaving CPU downloads broken (no GGUF routing).
        assert BaseLlamaCppEngine.USES_GGUF is True
        assert CPU_Engine.USES_GGUF is True
        assert CUDA_Engine.USES_GGUF is True

    def test_cpu_and_cuda_share_the_base_mapping(self):
        assert CPU_Engine.MODEL_MAPPING is BaseLlamaCppEngine.MODEL_MAPPING
        assert CUDA_Engine.MODEL_MAPPING is BaseLlamaCppEngine.MODEL_MAPPING
        assert len(BaseLlamaCppEngine.MODEL_MAPPING) > 0

    def test_gguf_values_are_repo_ids(self):
        for link, repo in BaseLlamaCppEngine.MODEL_MAPPING.items():
            assert repo.count("/") == 1, f"{link} → {repo} is not a 'owner/name' repo id"
            assert repo.endswith("-GGUF") or "GGUF" in repo, f"{link} → {repo} is not a GGUF repo"


class TestEveryCatalogModelHasRunnableQuant:
    """No catalogued model may be orphaned on an engine — else it would 401 (gated)
    or download the wrong format. This is the regression lock for the CPU gap."""

    @pytest.mark.parametrize("link", CATALOG_LINKS)
    def test_gguf_covers_catalog(self, link):
        assert link in BaseLlamaCppEngine.MODEL_MAPPING, (
            f"{link} has no public GGUF quant → would hit the gated safetensors on CPU/CUDA"
        )

    @pytest.mark.parametrize("link", CATALOG_LINKS)
    def test_mlx_covers_catalog(self, link):
        assert link in MLX_Engine.MODEL_MAPPING, (
            f"{link} has no MLX quant → would hit the gated safetensors on Apple Silicon"
        )

    def test_mlx_targets_are_public_community_quants(self):
        for link, repo in MLX_Engine.MODEL_MAPPING.items():
            assert repo.startswith("mlx-community/"), f"{link} → {repo} is not a public mlx-community quant"
