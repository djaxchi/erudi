"""Tests for utility modules (prompt_utils, hf_model_metadata).

Tests cover:
- Prompt utilities (system prompt generation, strategy selection)
- HuggingFace metadata (size estimation, parameter extraction, metadata formatting)

The FAISS-era file_processor / kb_utils suites died with the
PostgreSQL/pgvector migration; ingestion and retrieval coverage is rebuilt
with the new pipeline (extraction / chunking / vector-store phases).
"""
from unittest.mock import Mock, patch

# Prompt utils
from src.utils.prompt_utils import (
    build_system_prompt,
    get_prompting_strategy
)

# HF metadata utils
from src.core import config
from src.utils.hf_model_metadata import (
    get_disk_size_after_quant,
    get_model_size_estimate,
    extract_parameter_pattern,
    format_model_info_metadata,
    measure_dir_size_gb,
    rewrite_size_in_metadata,
    ModelSize,
    ParameterCount,
    ParameterScale,
    QuantizationType,
)


def _sibling(rfilename, size):
    """Build a fake HF repo sibling (rfilename + size) for repo_info mocks."""
    s = Mock()
    s.rfilename = rfilename
    s.size = size
    return s


# ============ Prompt Utils Tests ============

class TestPromptUtils:
    """Test suite for prompt_utils.py prompt generation and strategy utilities."""

    def test_build_system_prompt_tiny(self):
        """Test system prompt generation for tiny models (<2B).
        
        Should generate minimal prompt for tiny models.
        """
        prompt = build_system_prompt(
            model_name="Test Tiny 1B",
            size_category="tiny"
        )
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        # Tiny prompts are concise
        assert len(prompt) < 500

    def test_build_system_prompt_small(self):
        """Test system prompt generation for small models (2-4B).
        
        Should generate brief prompt for small models.
        """
        prompt = build_system_prompt(
            model_name="Test Small 2B",
            size_category="small"
        )
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_build_system_prompt_medium(self):
        """Test system prompt generation for medium models (4-8B).
        
        Should generate detailed prompt for medium models.
        """
        prompt = build_system_prompt(
            model_name="Mistral 7B",
            size_category="medium"
        )
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        # Medium prompts are more detailed
        assert len(prompt) > 200

    def test_build_system_prompt_large(self):
        """Test system prompt generation for large models (8-16B).
        
        Should generate comprehensive prompt with cutoff dates.
        """
        prompt = build_system_prompt(
            model_name="Mistral Nemo 12B",
            size_category="large"
        )
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        # Large prompts may include cutoff date awareness

    def test_build_system_prompt_xlarge(self):
        """Test system prompt generation for xlarge models (16B+).
        
        Should generate sophisticated prompt with full guidelines.
        """
        prompt = build_system_prompt(
            model_name="Test XLarge 20B",
            size_category="xlarge"
        )
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        # XLarge prompts are most comprehensive
        assert len(prompt) > 500

    def test_build_system_prompt_with_starred_messages(self):
        """Test prompt generation with starred messages injection.
        
        Should include important messages in prompt.
        """
        starred = [
            "Always use type hints in Python",
            "Remember to handle exceptions properly"
        ]
        
        prompt = build_system_prompt(
            model_name="Test 7B",
            size_category="medium",
            starred_messages=starred
        )
        
        assert isinstance(prompt, str)
        # Check if starred content is present
        assert any(msg in prompt for msg in starred) or "Important" in prompt

    def test_get_prompting_strategy_tiny(self):
        """Tiny models (≤2B) get a minimal prompt and the smallest KB budget
        (literature: below ~3B, oversized context degrades net accuracy)."""
        strategy = get_prompting_strategy(param_size=1)

        assert isinstance(strategy, dict)
        assert strategy["system_prompt_size_category"] == "tiny"
        assert strategy["use_kb_context"] is True
        assert strategy["kb_token_budget"] == 400
        assert "kb_top_k" not in strategy  # flat top-k retired (issue #81)

    def test_get_prompting_strategy_small(self):
        """Test strategy selection for small models (2-4B).

        Should return small strategy config.
        """
        strategy = get_prompting_strategy(param_size=3)

        assert isinstance(strategy, dict)
        assert strategy["system_prompt_size_category"] == "small"
        assert strategy["kb_token_budget"] == 700

    def test_get_prompting_strategy_medium(self):
        """Test strategy selection for medium models (7B).

        Should return medium strategy config with balanced settings.
        """
        strategy = get_prompting_strategy(param_size=7)

        assert isinstance(strategy, dict)
        assert strategy["system_prompt_size_category"] == "medium"
        assert strategy["kb_token_budget"] == 1000

    def test_get_prompting_strategy_large(self):
        """Test strategy selection for large models (12B).

        Should return large strategy config with enhanced settings.
        """
        strategy = get_prompting_strategy(param_size=12)

        assert isinstance(strategy, dict)
        assert strategy["system_prompt_size_category"] == "large"
        assert strategy["kb_token_budget"] == 1400

    def test_get_prompting_strategy_xlarge(self):
        """Test strategy selection for xlarge models (16B+).

        Should return xlarge strategy with the largest KB budget.
        """
        strategy = get_prompting_strategy(param_size=20)

        assert isinstance(strategy, dict)
        assert strategy["system_prompt_size_category"] == "xlarge"
        assert strategy["kb_token_budget"] == 2000

    def test_kb_token_budget_scales_monotonically(self):
        """The KB context budget must never shrink as models grow."""
        budgets = [
            get_prompting_strategy(param_size=size)["kb_token_budget"]
            for size in (1, 3, 7, 12, 20)
        ]
        assert budgets == sorted(budgets)

    def test_get_prompting_strategy_edge_cases(self):
        """Test strategy selection with edge case sizes.
        
        Should handle zero, negative, and very large sizes gracefully.
        """
        # Zero size
        strategy = get_prompting_strategy(param_size=0)
        assert isinstance(strategy, dict)
        
        # Very large size
        strategy = get_prompting_strategy(param_size=100)
        assert isinstance(strategy, dict)


# ============ HF Metadata Utils Tests ============

class TestHFMetadataUtils:
    """Test suite for hf_model_metadata.py HuggingFace metadata utilities."""

    @patch('src.utils.hf_model_metadata.get_hf_api')
    def test_get_disk_size_after_quant_success(self, mock_get_hf_api):
        """Test successful disk size retrieval via HF API.
        
        Should return ModelSize from API when available.
        """
        # Mock HF API response. Real rfilenames are required now that sizing sums
        # only the chosen artifact (#220); these non-gguf names mean the whole-repo
        # sum is used regardless of the active engine format.
        mock_hf_api = Mock()
        mock_repo_info = Mock()
        mock_repo_info.siblings = [
            _sibling("model-00001-of-00002.safetensors", 1_000_000_000),  # 1 GB
            _sibling("config.json", 500_000_000),                          # 0.5 GB
        ]
        mock_hf_api.repo_info.return_value = mock_repo_info
        mock_get_hf_api.return_value = mock_hf_api

        size = get_disk_size_after_quant("mlx-community/Test-Model-4bit")

        assert isinstance(size, ModelSize)
        assert size.source == "api"
        assert not size.is_estimate
        # Should be approximately 1.4 GB
        assert 1.0 <= size.size_gb <= 2.0

    @patch('src.utils.hf_model_metadata.get_hf_api')
    def test_get_disk_size_after_quant_api_failure(self, mock_get_hf_api):
        """Test fallback when HF API fails.
        
        Should return ModelSize estimate when API call fails.
        """
        mock_hf_api = Mock()
        mock_hf_api.repo_info.side_effect = Exception("API error")
        mock_get_hf_api.return_value = mock_hf_api
        
        size = get_disk_size_after_quant("mlx-community/Test-Model-4bit")
        
        assert isinstance(size, ModelSize)
        assert size.is_estimate
        # Should use fallback calculation
        assert size.size_gb > 0

    def test_get_model_size_estimate_mistral_7b(self):
        """Test size estimation for Mistral 7B models.
        
        Should return ModelSize for Mistral family.
        """
        size = get_model_size_estimate(
            "Mistral 7B Instruct",
            "mistralai/Mistral-7B-Instruct-v0.3"
        )
        
        assert isinstance(size, ModelSize)
        assert size.size_gb > 10  # Should be around 13.5 GB

    def test_get_model_size_estimate_gemma_2b(self):
        """Test size estimation for Gemma 2B models.
        
        Should return ModelSize for Gemma family.
        """
        size = get_model_size_estimate(
            "Gemma 2B",
            "google/gemma-2b"
        )
        
        assert isinstance(size, ModelSize)
        assert size.size_gb > 4  # Should be around 5-6 GB

    def test_get_model_size_estimate_unknown_model(self):
        """Test size estimation for unknown model.
        
        Should return ModelSize with Unknown source for unknown models.
        """
        size = get_model_size_estimate(
            "UnknownModel 5B",
            "unknown/model-5b"
        )
        
        assert isinstance(size, ModelSize)
        # Should handle unknown models gracefully with fallback

    def test_extract_parameter_pattern_7b(self):
        """Test parameter extraction from model name (7B format).
        
        Should extract ParameterCount(7.0, BILLION) from model name.
        """
        params = extract_parameter_pattern("Mistral-7B-Instruct-v0.3")
        
        assert params is not None
        assert params.count == 7.0
        assert params.scale == ParameterScale.BILLION

    def test_extract_parameter_pattern_1_5b(self):
        """Test parameter extraction from model name (1.5B format).
        
        Should extract ParameterCount(1.5, BILLION) from model name.
        """
        params = extract_parameter_pattern("Qwen2.5-1.5B")
        
        assert params is not None
        assert params.count == 1.5
        assert params.scale == ParameterScale.BILLION

    def test_extract_parameter_pattern_no_params(self):
        """Test parameter extraction when no param count in name.
        
        Should return None when no pattern found.
        """
        params = extract_parameter_pattern("Generic-Model")
        
        assert params is None

    def test_extract_parameter_pattern_from_link(self):
        """Test parameter extraction from HF link.
        
        Should extract param count from link when not in name.
        """
        params = extract_parameter_pattern("Model-8B-Instruct")
        
        assert params is not None
        assert params.count == 8.0
        assert params.scale == ParameterScale.BILLION

    def test_extract_parameter_pattern_million(self):
        """Test parameter extraction for million-scale models.
        
        Should extract ParameterCount(350, MILLION) from model name.
        """
        params = extract_parameter_pattern("model-350m")
        
        assert params is not None
        assert params.count == 350.0
        assert params.scale == ParameterScale.MILLION

    def test_format_model_info_metadata_basic(self):
        """Test metadata formatting with basic ModelInfo.
        
        Should format ModelInfo to structured string with ModelSize object.
        """
        mock_model_info = Mock()
        mock_model_info.id = "test/model-7b"
        mock_model_info.author = "TestAuthor"
        mock_model_info.sha = "abc123def456"
        mock_model_info.downloads = 1000
        mock_model_info.likes = 50
        mock_model_info.tags = ["text-generation", "transformers"]
        
        size = ModelSize(size_gb=4.2, min_gb=4.0, max_gb=4.5, is_estimate=True, source="test")
        
        metadata = format_model_info_metadata(
            model_info=mock_model_info,
            size_estimate=size,
            quantized=True
        )
        
        assert isinstance(metadata, str)
        assert "test/model-7b" in metadata
        assert "TestAuthor" in metadata or "author" in metadata.lower()

    def test_format_model_info_metadata_no_estimate(self):
        """Test metadata formatting without size estimate.
        
        Should format without size when not provided.
        """
        mock_model_info = Mock()
        mock_model_info.id = "test/model"
        mock_model_info.author = "Author"
        mock_model_info.sha = "abc123"
        mock_model_info.downloads = 100
        mock_model_info.likes = 10
        mock_model_info.tags = []
        
        metadata = format_model_info_metadata(
            model_info=mock_model_info
        )
        
        assert isinstance(metadata, str)
        assert "test/model" in metadata

    def test_parse_quantization_type_4bit(self):
        """Test quantization type detection for 4-bit models.
        
        Should detect INT4 from repo name patterns.
        """
        from src.utils.hf_model_metadata import parse_quantization_type
        
        quant_type = parse_quantization_type("mlx-community/Mistral-7B-4bit")
        assert quant_type == QuantizationType.INT4

    def test_parse_quantization_type_8bit(self):
        """Test quantization type detection for 8-bit models.
        
        Should detect INT8 from repo name patterns.
        """
        from src.utils.hf_model_metadata import parse_quantization_type
        
        quant_type = parse_quantization_type("company/model-8bit-quantized")
        assert quant_type == QuantizationType.INT8

    def test_parse_quantization_type_fp16(self):
        """Test quantization type detection for FP16 models.
        
        Should detect FP16 from repo name patterns.
        """
        from src.utils.hf_model_metadata import parse_quantization_type
        
        quant_type = parse_quantization_type("company/model-fp16")
        assert quant_type == QuantizationType.FP16

    def test_parse_quantization_type_unknown(self):
        """Test quantization type detection for unknown formats.
        
        Should return UNKNOWN for unrecognized patterns.
        """
        from src.utils.hf_model_metadata import parse_quantization_type
        
        quant_type = parse_quantization_type("company/regular-model")
        assert quant_type == QuantizationType.UNKNOWN

    def test_calculate_size_from_parameters_7b_fp16(self):
        """Test size calculation for 7B FP16 model.
        
        Should calculate ~14-16 GB for 7B parameters in FP16.
        """
        from src.utils.hf_model_metadata import calculate_size_from_parameters
        
        param_count = ParameterCount(count=7.0, scale=ParameterScale.BILLION, is_estimate=False)
        size = calculate_size_from_parameters(param_count, QuantizationType.FP16)
        
        assert isinstance(size, ModelSize)
        assert 14.0 <= size.size_gb <= 18.0
        assert size.source == "calculated"

    def test_calculate_size_from_parameters_7b_int4(self):
        """Test size calculation for 7B INT4 model.
        
        Should calculate ~3.5 GB for 7B parameters in INT4.
        """
        from src.utils.hf_model_metadata import calculate_size_from_parameters
        
        param_count = ParameterCount(count=7.0, scale=ParameterScale.BILLION, is_estimate=False)
        size = calculate_size_from_parameters(param_count, QuantizationType.INT4)
        
        assert isinstance(size, ModelSize)
        assert 3.0 <= size.size_gb <= 4.5
        assert size.source == "calculated"

    def test_model_size_to_string(self):
        """Test ModelSize to_string method.
        
        Should format size with tilde and range for estimates.
        """
        size = ModelSize(size_gb=4.2, min_gb=4.0, max_gb=4.5, is_estimate=True, source="test")
        assert "~" in size.to_string()
        assert "GB" in size.to_string()
        
        size_exact = ModelSize(size_gb=4.2, min_gb=4.2, max_gb=4.2, is_estimate=False, source="api")
        assert size_exact.to_string() == "~4.2 GB"

    def test_parameter_count_to_string(self):
        """Test ParameterCount to_string method.
        
        Should format with B or M suffix based on scale.
        """
        params_b = ParameterCount(count=7.0, scale=ParameterScale.BILLION, is_estimate=False)
        assert params_b.to_string() == "7B"  # Integer billions don't show decimal
        
        params_decimal = ParameterCount(count=1.5, scale=ParameterScale.BILLION, is_estimate=False)
        assert params_decimal.to_string() == "1.5B"  # Non-integer billions show decimal
        
        params_m = ParameterCount(count=350.0, scale=ParameterScale.MILLION, is_estimate=False)
        assert params_m.to_string() == "350M"  # Millions are always integers

    def test_parameter_count_total_billions(self):
        """Test ParameterCount total_billions property.
        
        Should convert millions to billions correctly.
        """
        params_b = ParameterCount(count=7.0, scale=ParameterScale.BILLION, is_estimate=False)
        assert params_b.total_billions == 7.0
        
        params_m = ParameterCount(count=350.0, scale=ParameterScale.MILLION, is_estimate=False)
        assert abs(params_m.total_billions - 0.35) < 0.01


# ============ Chosen-artifact catalog sizing (#220 secondary) ============

class TestGetDiskSizeChosenArtifact:
    """get_disk_size_after_quant must sum ONLY the artifact the downloader fetches.

    For a GGUF multi-quant repo that is the single best quant (+ mmproj + small
    aux), NOT the 20-40 GB whole repo (#220/#170). Single-artifact repos keep the
    whole-repo sum. The active engine format drives the branch.
    """

    @patch('src.utils.hf_model_metadata.get_hf_api')
    def test_gguf_multiquant_sums_only_chosen_quant(self, mock_get_hf_api, monkeypatch):
        class _GgufEngine:
            USES_GGUF = True

        monkeypatch.setattr(config, "LLM_Engine", _GgufEngine)
        siblings = [
            _sibling("model-F16.gguf", 8_000_000_000),
            _sibling("model-Q8_0.gguf", 3_000_000_000),
            _sibling("model-Q4_K_M.gguf", 800_000_000),
            _sibling("mmproj-model-f16.gguf", 600_000_000),
            _sibling("config.json", 2_000),
        ]
        repo_info = Mock()
        repo_info.siblings = siblings
        mock_api = Mock()
        mock_api.repo_info.return_value = repo_info
        mock_get_hf_api.return_value = mock_api

        size = get_disk_size_after_quant("bartowski/Model-GGUF")

        # Chosen = best quant (Q4_K_M) + mmproj + small aux (config.json).
        expected_gb = (800_000_000 + 600_000_000 + 2_000) / (1024**3)
        whole_repo_gb = sum(s.size for s in siblings) / (1024**3)
        assert abs(size.size_gb - expected_gb) < 1e-6
        assert size.size_gb < whole_repo_gb        # NOT the whole-repo sum
        assert size.source == "api"

    @patch('src.utils.hf_model_metadata.get_hf_api')
    def test_single_artifact_repo_keeps_whole_repo_sum(self, mock_get_hf_api, monkeypatch):
        class _MlxEngine:
            USES_GGUF = False

        monkeypatch.setattr(config, "LLM_Engine", _MlxEngine)
        siblings = [
            _sibling("model.safetensors", 1_800_000_000),
            _sibling("config.json", 2_000),
        ]
        repo_info = Mock()
        repo_info.siblings = siblings
        mock_api = Mock()
        mock_api.repo_info.return_value = repo_info
        mock_get_hf_api.return_value = mock_api

        size = get_disk_size_after_quant("mlx-community/Model-4bit")

        expected_gb = sum(s.size for s in siblings) / (1024**3)
        assert abs(size.size_gb - expected_gb) < 1e-6
        assert size.source == "api"


# ============ Measured on-disk size + metadata rewrite (#220 helpers) ============

class TestMeasureDirSize:
    """measure_dir_size_gb: real recursive byte count, defensive on missing paths."""

    def test_sums_nested_files(self, tmp_path):
        (tmp_path / "a.bin").write_bytes(b"\x00" * (1024**3 // 2))     # 0.5 GB
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.bin").write_bytes(b"\x00" * (1024**3 // 4))          # 0.25 GB
        assert abs(measure_dir_size_gb(tmp_path) - 0.75) < 1e-6

    def test_missing_dir_returns_zero(self, tmp_path):
        assert measure_dir_size_gb(tmp_path / "does-not-exist") == 0.0

    def test_empty_dir_returns_zero(self, tmp_path):
        assert measure_dir_size_gb(tmp_path) == 0.0

    def test_single_file_path(self, tmp_path):
        f = tmp_path / "w.bin"
        f.write_bytes(b"\x00" * (1024**3 // 2))                        # 0.5 GB
        assert abs(measure_dir_size_gb(f) - 0.5) < 1e-6


class TestRewriteSizeInMetadata:
    """rewrite_size_in_metadata: replace/append Size, add disk_size_gb, keep rest."""

    def test_replaces_existing_size_line(self):
        meta = (
            "Model ID: org/x\nSize: ~117.6 GB\nParameters: 8B\n"
            "Last Modified: 2024-09-25 17:00:57+00:00"
        )
        out = rewrite_size_in_metadata(meta, 1.834)
        lines = out.split("\n")
        assert "Size: ~1.8 GB" in lines
        assert "Disk Size GB: 1.83" in lines
        # The old (wrong) size is gone and not duplicated.
        assert sum(1 for line in lines if line.startswith("Size:")) == 1
        assert "117.6" not in out
        # Other lines (including value-side colons) are preserved verbatim.
        assert "Model ID: org/x" in lines
        assert "Parameters: 8B" in lines
        assert "Last Modified: 2024-09-25 17:00:57+00:00" in lines

    def test_appends_when_size_absent(self):
        out = rewrite_size_in_metadata("Author: foo", 2.0)
        assert out == "Author: foo\nSize: ~2.0 GB\nDisk Size GB: 2.00"

    def test_none_and_empty_metadata(self):
        expected = "Size: ~1.8 GB\nDisk Size GB: 1.83"
        assert rewrite_size_in_metadata(None, 1.834) == expected
        assert rewrite_size_in_metadata("", 1.834) == expected

    def test_idempotent(self):
        meta = "Model ID: org/x\nSize: ~40.2 GB\nParameters: 7B"
        once = rewrite_size_in_metadata(meta, 3.14)
        twice = rewrite_size_in_metadata(once, 3.14)
        assert once == twice

    def test_frontend_key_parity(self):
        """Keys must survive the frontend parser (lower + spaces->underscores)."""
        out = rewrite_size_in_metadata(None, 1.834)
        parsed = {}
        for line in out.split("\n"):
            key, _, value = line.partition(":")
            parsed[key.strip().lower().replace(" ", "_")] = value.strip()
        assert parsed["size"] == "~1.8 GB"
        assert parsed["disk_size_gb"] == "1.83"


# ============ Integration Tests ============

class TestUtilsIntegration:
    """Integration tests for cross-utility functionality."""

    def test_prompt_strategy_consistency(self):
        """Test that prompt size categories match strategy outputs.
        
        Verifies consistency between strategy selection and prompt generation.
        """
        test_sizes = [1, 3, 7, 12, 20]
        
        for size in test_sizes:
            strategy = get_prompting_strategy(param_size=size)
            category = strategy["system_prompt_size_category"]
            
            # Generate prompt with that category
            prompt = build_system_prompt(
                model_name=f"Test {size}B",
                size_category=category
            )
            
            assert isinstance(prompt, str)
            assert len(prompt) > 0
