"""Catalog ↔ engine quant-mapping invariants (#95).

These guard the token-free-by-construction design: every catalogued base model
must resolve to a public quant in the active engine's format (MLX on Apple
Silicon, GGUF on CPU/CUDA), so a download never hits the gated first-party
safetensors. They are pure class-attribute checks — no network, CI-safe.
"""

import pytest

from src.core import config
from src.core.exceptions import UnsupportedPlatformException
from src.database.seed import Database_Seeder
from src.domains.llms import services
from src.utils.hf_model_metadata import humanize_model_name
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


class TestHumanizedNames:
    """Display names are derived from the real slug — exact, unambiguous, no
    hand-written 'Gemma-4B' that actually hides Gemma 3 4B."""

    @pytest.mark.parametrize("link,expected", [
        ("google/gemma-3-270m-it",                "Gemma 3 270M Instruct"),
        ("google/gemma-2-2b-it",                  "Gemma 2 2B Instruct"),     # was "Gemma-2B"
        ("google/gemma-3-4b-it",                  "Gemma 3 4B Instruct"),     # was the ambiguous "Gemma-4B"
        ("google/gemma-3-12b-it",                 "Gemma 3 12B Instruct"),
        ("google/gemma-4-E2B-it",                 "Gemma 4 E2B Instruct"),
        ("google/gemma-4-26b-a4b-it",             "Gemma 4 26B A4B Instruct"),
        ("google/gemma-4-31b-it",                 "Gemma 4 31B Instruct"),
        ("mistralai/Mistral-7B-Instruct-v0.3",    "Mistral 7B Instruct v0.3"),
        ("mistralai/Ministral-8B-Instruct-2410",  "Ministral 8B Instruct 2410"),
        ("mistralai/Mistral-Nemo-Instruct-2407",  "Mistral Nemo Instruct 2407"),
        ("meta-llama/Llama-3.1-8B-Instruct",      "Llama 3.1 8B Instruct"),
        ("Qwen/Qwen2.5-7B-Instruct",              "Qwen2.5 7B Instruct"),
        ("Qwen/Qwen2.5-VL-3B-Instruct",           "Qwen2.5 VL 3B Instruct"),
    ])
    def test_humanize(self, link, expected):
        assert humanize_model_name(link) == expected

    def test_no_catalog_name_is_ambiguous_gemma(self):
        # No catalogued Gemma renders as a bare "Gemma N B" without its family version.
        for link in CATALOG_LINKS:
            name = humanize_model_name(link)
            if name.startswith("Gemma"):
                # second token must be the family version (a number), never the size
                assert name.split()[1].replace(".", "").isdigit(), f"ambiguous: {name}"


class TestDownloadRunnabilityGuard:
    """download_llm rejects non-runnable targets up front (clear error, no 401→500)."""

    def test_rejects_gated_base_with_no_quant(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_Engine", CPU_Engine)
        # unmapped gated base id → resolves to itself → not GGUF format → rejected
        with pytest.raises(UnsupportedPlatformException):
            services._assert_runnable("google/some-gated-model-it", "google/some-gated-model-it")

    def test_allows_mapped_public_quant(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_Engine", CPU_Engine)
        # resolved GGUF quant → runnable → no raise
        services._assert_runnable("google/gemma-3-1b-it", "unsloth/gemma-3-1b-it-GGUF")
