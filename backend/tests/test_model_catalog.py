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


class TestRunnabilityPredicate:
    """is_runnable is capability-based (engine format minus KNOWN_BROKEN), never an
    allowlist — so community fine-tunes in the right format are not over-blocked."""

    def test_mlx_runs_community_quants_and_curated(self):
        assert MLX_Engine.is_runnable("mlx-community/gemma-3-1b-it-4bit") is True
        # a community fine-tune nobody curated, but in MLX format → runnable
        assert MLX_Engine.is_runnable("mlx-community/some-cool-distill-4bit") is True

    def test_mlx_bans_gated_base_and_known_broken(self):
        # gated first-party safetensors id (never converted) → not MLX format
        assert MLX_Engine.is_runnable("google/gemma-3-1b-it") is False
        # downloads but crashes at load on mlx-vlm 0.6.2
        assert MLX_Engine.is_runnable("mlx-community/gemma-4-e2b-it-4bit") is False
        assert "mlx-community/gemma-4-e2b-it-4bit" in MLX_Engine.KNOWN_BROKEN

    def test_llamacpp_runs_gguf_community_and_curated(self):
        assert CPU_Engine.is_runnable("unsloth/gemma-3-1b-it-GGUF") is True
        assert CUDA_Engine.is_runnable("bartowski/Qwen2.5-7B-Instruct-GGUF") is True
        # community fine-tune GGUF nobody curated → still runnable (not over-blocked)
        assert CPU_Engine.is_runnable("someuser/My-Cool-Finetune-GGUF") is True

    def test_llamacpp_bans_gated_base_safetensors(self):
        assert CPU_Engine.is_runnable("google/gemma-3-1b-it") is False
        assert CPU_Engine.is_runnable("meta-llama/Llama-3.1-8B-Instruct") is False

    def test_every_catalog_model_is_runnable_on_some_engine(self):
        # Each curated base resolves to a runnable quant on BOTH engines (its mapped
        # target), except KNOWN_BROKEN exclusions which must still run on the other.
        for link in CATALOG_LINKS:
            mlx_target = MLX_Engine.MODEL_MAPPING[link]
            gguf_target = CPU_Engine.MODEL_MAPPING[link]
            assert MLX_Engine.is_runnable(mlx_target) or CPU_Engine.is_runnable(gguf_target), (
                f"{link} is runnable on neither engine"
            )
