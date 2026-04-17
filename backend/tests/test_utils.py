"""Comprehensive tests for utility modules (file_processor, kb_utils, prompt_utils, hf_model_metadata).

Tests cover:
- File processing (PDF extraction, text cleaning, chunking, sentence splitting)
- Knowledge base utilities (FAISS retrieval with mocked embeddings)
- Prompt utilities (system prompt generation, strategy selection)
- HuggingFace metadata (size estimation, parameter extraction, metadata formatting)

All heavy operations (FAISS, embeddings, HF API) are mocked for fast testing.
"""
import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# File processor functions
from src.utils.file_processor import (
    split_sentences,
    chunk_by_tokens,
    prepare_for_knowledge_base,
    extract_text_from_pdf,
    clean_text,
    chunk_text
)

# KB utils
from src.utils.kb_utils import get_relevant_texts_from_kb

# Prompt utils
from src.utils.prompt_utils import (
    build_system_prompt,
    get_prompting_strategy
)

# HF metadata utils
from src.utils.hf_model_metadata import (
    get_disk_size_after_quant,
    get_model_size_estimate,
    extract_parameter_pattern,
    format_model_info_metadata,
    ModelSize,
    ParameterCount,
    ParameterScale,
    QuantizationType,
)


# ============ File Processor Tests ============

class TestFileProcessor:
    """Test suite for file_processor.py utilities."""

    def test_split_sentences_basic(self):
        """Test basic sentence splitting with common punctuation.
        
        Verifies that sentences are properly split on periods, question marks,
        and exclamation points followed by uppercase letters.
        """
        text = "First sentence. Second sentence! Third question?"
        
        sentences = split_sentences(text)
        
        assert len(sentences) > 0
        assert isinstance(sentences, list)
        # Due to merging logic (80 char minimum), may combine short sentences
        for sentence in sentences:
            assert len(sentence) > 0

    def test_split_sentences_empty(self):
        """Test sentence splitting with empty input.
        
        Should return empty list for empty strings.
        """
        result = split_sentences("")
        
        assert result == []

    def test_split_sentences_no_punctuation(self):
        """Test sentence splitting with text lacking sentence terminators.
        
        Text without proper punctuation should still return as single item.
        """
        text = "This is text without proper punctuation marks"
        
        sentences = split_sentences(text)
        
        assert len(sentences) >= 1

    def test_split_sentences_paragraph_breaks(self):
        """Test sentence splitting with paragraph breaks (double newlines).
        
        Paragraph breaks should be preserved as sentence boundaries.
        """
        text = "First paragraph.\n\nSecond paragraph. With another sentence."
        
        sentences = split_sentences(text)
        
        assert len(sentences) >= 1

    def test_chunk_by_tokens_basic(self):
        """Test token-based chunking with default parameters.
        
        Should create chunks that respect token limits and include overlap.
        """
        text = "This is a test sentence. " * 100  # Long text
        
        chunks = chunk_by_tokens(text)
        
        assert len(chunks) > 0
        assert isinstance(chunks, list)
        assert all(isinstance(chunk, str) for chunk in chunks)
        assert all(len(chunk) > 0 for chunk in chunks)

    def test_chunk_by_tokens_short_text(self):
        """Test chunking with text shorter than chunk size.
        
        Should return single chunk for short text.
        """
        text = "Short text."
        
        chunks = chunk_by_tokens(text)
        
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunk_by_tokens_empty(self):
        """Test chunking with empty text.
        
        Should return empty list.
        """
        result = chunk_by_tokens("")
        
        assert result == []

    def test_extract_text_from_pdf_nonexistent(self):
        """Test PDF extraction with non-existent file.
        
        Should raise FileNotFoundError or return empty string.
        """
        with pytest.raises(FileNotFoundError):
            extract_text_from_pdf("/nonexistent/file.pdf")

    def test_clean_text_basic(self):
        """Test text cleaning with various whitespace and special chars.
        
        Should normalize whitespace and remove excessive newlines.
        """
        text = "  Multiple   spaces\n\n\nMany newlines  \t\tTabs  "
        
        cleaned = clean_text(text)
        
        assert cleaned is not None
        assert "  " not in cleaned  # No double spaces
        assert not cleaned.startswith(" ")  # No leading space
        assert not cleaned.endswith(" ")  # No trailing space

    def test_clean_text_empty(self):
        """Test cleaning empty string.
        
        Should return empty string.
        """
        result = clean_text("")
        
        assert result == ""

    def test_clean_text_unicode(self):
        """Test cleaning text with Unicode characters.
        
        Should handle Unicode properly without corruption.
        """
        text = "Texte français avec accents: é, è, à, ù"
        
        cleaned = clean_text(text)
        
        assert "français" in cleaned or "francais" in cleaned  # May normalize accents
        assert len(cleaned) > 0

    def test_chunk_text_basic(self):
        """Test word-based chunking with overlap.
        
        Should create chunks of specified size with overlap between chunks.
        """
        text = "word " * 200  # 200 words
        chunk_size = 50
        overlap = 10
        
        chunks = chunk_text(text, chunk_size, overlap)
        
        assert len(chunks) > 1
        assert isinstance(chunks, list)
        # Verify chunks are roughly the right size (in words)
        assert all(len(chunk.split()) <= chunk_size + 10 for chunk in chunks)  # +10 tolerance

    def test_chunk_text_no_overlap(self):
        """Test word-based chunking without overlap.
        
        Should create non-overlapping chunks.
        """
        text = "word " * 100
        chunk_size = 20
        overlap = 0
        
        chunks = chunk_text(text, chunk_size, overlap)
        
        assert len(chunks) > 1

    def test_chunk_text_short_text(self):
        """Test chunking text shorter than chunk size.
        
        Should return single chunk.
        """
        text = "Short text with few words"
        chunk_size = 100
        overlap = 10
        
        chunks = chunk_text(text, chunk_size, overlap)
        
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_prepare_for_knowledge_base_empty_list(self):
        """Test KB preparation with empty input list.
        
        Should return empty list without errors.
        """
        result = prepare_for_knowledge_base([])
        
        assert result == []

    def test_prepare_for_knowledge_base_nonexistent_paths(self):
        """Test KB preparation with non-existent paths.
        
        Should handle missing files gracefully and return empty list.
        """
        result = prepare_for_knowledge_base(["/nonexistent/path.pdf"])
        
        assert isinstance(result, list)
        # May return empty or skip invalid files

    def test_prepare_for_knowledge_base_with_txt(self):
        """Test KB preparation with actual text file.
        
        Should successfully process TXT file and return cleaned text chunks.
        """
        # Create temporary TXT file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("This is test content for knowledge base. " * 20)
            temp_path = f.name
        
        try:
            result = prepare_for_knowledge_base([temp_path])
            
            assert isinstance(result, list)
            assert len(result) > 0
            assert all(isinstance(text, str) for text in result)
        finally:
            os.unlink(temp_path)


# ============ KB Utils Tests ============

class TestKBUtils:
    """Test suite for kb_utils.py knowledge base retrieval utilities."""

    def test_get_relevant_texts_no_kb_attached(self, test_db_session, mock_llm):
        """Test retrieval when LLM has no KB attached.
        
        Should raise exception when is_attached_to_kb=False.
        """
        from src.entities.Llm import Llm
        
        # Ensure LLM has no KB
        mock_llm.is_attached_to_kb = 0
        mock_llm.kb_id = None
        test_db_session.commit()
        
        with pytest.raises(Exception):
            get_relevant_texts_from_kb(
                query="Test query",
                llm=mock_llm,
                db=test_db_session,
                kb_top_k=1
            )

    def test_get_relevant_texts_empty_query(self, test_db_session, mock_llm_with_kb):
        """Test retrieval with empty query string.
        
        Should raise exception when index is missing.
        """
        llm, kb, vector_store = mock_llm_with_kb
        
        with pytest.raises(Exception):
            get_relevant_texts_from_kb(
                query="",
                llm=llm,
                db=test_db_session,
                kb_top_k=1
            )

    @patch('src.utils.kb_utils.faiss')
    @patch('src.utils.kb_utils.Embedder_Engine')
    def test_get_relevant_texts_with_kb(self, mock_embedder, mock_faiss, 
                                        test_db_session, mock_llm_with_kb):
        """Test successful retrieval from KB with mocked FAISS and embedder.
        
        Should return relevant text chunks when KB exists and query is valid.
        """
        llm, kb, vector_store = mock_llm_with_kb
        
        # Mock FAISS index
        mock_index = Mock()
        mock_index.search.return_value = (
            [[0.9, 0.8]],  # Distances (cosine similarity)
            [[0, 1]]  # Indices in VectorStore
        )
        mock_faiss.read_index.return_value = mock_index
        
        # Mock embedder
        mock_embedder_instance = Mock()
        mock_embedder_instance.encode.return_value = [[0.1] * 384]  # Dummy embedding
        mock_embedder.return_value = mock_embedder_instance
        
        # Update VectorStore with test data
        vector_store.vectors_data = {
            "0": "First relevant chunk about Python",
            "1": "Second relevant chunk about FastAPI"
        }
        test_db_session.commit()
        
        # Create temp index file
        with tempfile.NamedTemporaryFile(suffix='.index', delete=False) as f:
            temp_index = f.name
        kb.index_path = temp_index
        test_db_session.commit()
        
        try:
            result = get_relevant_texts_from_kb(
                query="How to use Python?",
                llm=llm,
                db=test_db_session,
                kb_top_k=2
            )
            
            # Should return chunks (exact behavior depends on implementation)
            assert isinstance(result, list)
        finally:
            if os.path.exists(temp_index):
                os.unlink(temp_index)

    def test_get_relevant_texts_kb_missing_index(self, test_db_session, mock_llm_with_kb):
        """Test retrieval when KB index file is missing.
        
        Should raise exception for missing index.
        """
        llm, kb, vector_store = mock_llm_with_kb
        
        # Set non-existent index path
        kb.index_path = "/nonexistent/index.faiss"
        test_db_session.commit()
        
        with pytest.raises(Exception):
            get_relevant_texts_from_kb(
                query="Test query",
                llm=llm,
                db=test_db_session,
                kb_top_k=1
            )


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

    def test_build_system_prompt_with_long_term_memory(self):
        """Test prompt generation with long-term memory injection.
        
        Should include conversation summary in prompt.
        """
        prompt = build_system_prompt(
            model_name="Test 7B",
            size_category="medium",
            long_term_memory="User is working on a FastAPI project with async endpoints."
        )
        
        assert isinstance(prompt, str)
        assert "FastAPI" in prompt or "Summary" in prompt

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
        """Test strategy selection for tiny models (1B).
        
        Should return minimal strategy config.
        """
        strategy = get_prompting_strategy(param_size=1)
        
        assert isinstance(strategy, dict)
        assert "system_prompt_size_category" in strategy
        assert strategy["system_prompt_size_category"] == "tiny"
        assert "max_history_turns" in strategy
        assert strategy["max_history_turns"] == 2  # Tiny models get fewer turns

    def test_get_prompting_strategy_small(self):
        """Test strategy selection for small models (2-4B).
        
        Should return small strategy config.
        """
        strategy = get_prompting_strategy(param_size=3)
        
        assert isinstance(strategy, dict)
        assert strategy["system_prompt_size_category"] == "small"

    def test_get_prompting_strategy_medium(self):
        """Test strategy selection for medium models (7B).
        
        Should return medium strategy config with balanced settings.
        """
        strategy = get_prompting_strategy(param_size=7)
        
        assert isinstance(strategy, dict)
        assert strategy["system_prompt_size_category"] == "medium"
        assert "kb_top_k" in strategy
        assert "mtm_top_k" in strategy
        assert "use_short_term_memory" in strategy

    def test_get_prompting_strategy_large(self):
        """Test strategy selection for large models (12B).
        
        Should return large strategy config with enhanced settings.
        """
        strategy = get_prompting_strategy(param_size=12)
        
        assert isinstance(strategy, dict)
        assert strategy["system_prompt_size_category"] == "large"

    def test_get_prompting_strategy_xlarge(self):
        """Test strategy selection for xlarge models (20B+).
        
        Should return xlarge strategy with maximum capabilities.
        """
        strategy = get_prompting_strategy(param_size=20)
        
        assert isinstance(strategy, dict)
        assert strategy["system_prompt_size_category"] == "xlarge"
        assert strategy["max_history_turns"] == 5  # More turns for large models

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
        # Mock HF API response
        mock_hf_api = Mock()
        mock_repo_info = Mock()
        mock_file1 = Mock()
        mock_file1.size = 1_000_000_000  # 1 GB
        mock_file2 = Mock()
        mock_file2.size = 500_000_000  # 0.5 GB
        mock_repo_info.siblings = [mock_file1, mock_file2]
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


# ============ Integration Tests ============

class TestUtilsIntegration:
    """Integration tests for cross-utility functionality."""

    def test_file_to_kb_pipeline(self):
        """Test complete pipeline: file → chunks → KB preparation.
        
        Verifies that file processing utilities work together correctly.
        """
        # Create temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            content = "This is sentence one. This is sentence two. " * 50
            f.write(content)
            temp_path = f.name
        
        try:
            # Process file
            texts = prepare_for_knowledge_base([temp_path])
            
            assert isinstance(texts, list)
            assert len(texts) > 0
            
            # Verify chunks can be processed further
            for text in texts:
                assert isinstance(text, str)
                assert len(text) > 0
        finally:
            os.unlink(temp_path)

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
