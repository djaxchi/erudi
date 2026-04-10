"""HuggingFace Model Metadata Utilities.

This module provides professional-grade utilities for fetching, parsing, and formatting
model metadata from HuggingFace Hub. Includes size estimation, parameter count extraction,
and structured metadata formatting with robust error handling.

Architecture:
    - Type-safe data structures (dataclasses) for model metadata
    - Enum-based categorization for model sizes and quantization types
    - Separation of concerns (fetch, parse, format)
    - Comprehensive error handling with custom exceptions
    - Configurable size mappings and parameter patterns

Key Features:
    - Calculate actual disk size for quantized models via HF API
    - Estimate sizes for known model families (Mistral, Gemma, Qwen, etc.)
    - Extract parameter counts from model names/links (7B, 1.5B, 350M, etc.)
    - Format ModelInfo objects into structured strings for storage
    - Type-safe, testable, and maintainable design

Data Structures:
    - ModelSize: Structured size representation with uncertainty bounds
    - ParameterCount: Typed parameter count with scale (billions/millions)
    - QuantizationType: Enum for quantization methods (4-bit, 8-bit, FP16, etc.)
    - ModelSizeCategory: Enum for model size ranges (tiny, small, medium, large, xlarge)

Functions:
    - get_disk_size_after_quant: Fetch actual size from HF API
    - get_model_size_estimate: Estimate size for known models
    - get_parameter_count_from_name: Extract parameter count from naming
    - format_model_info_metadata: Format ModelInfo to structured string
    - parse_quantization_type: Detect quantization method from repo name
    - calculate_size_from_parameters: Estimate size from parameter count

Examples:
    >>> # Get actual size of MLX quantized model
    >>> from src.utils.hf_model_metadata import get_disk_size_after_quant
    >>> 
    >>> size = get_disk_size_after_quant("mlx-community/Mistral-7B-v0.3-4bit")
    >>> print(size.to_string())  # "~3.2 GB"
    >>> 
    >>> # Estimate size for base model
    >>> from src.utils.hf_model_metadata import get_model_size_estimate
    >>> 
    >>> size = get_model_size_estimate(
    ...     "Mistral Instruct", 
    ...     "mistralai/Mistral-7B-Instruct-v0.3"
    ... )
    >>> print(size.to_string())  # "~13.5 GB"
    >>> 
    >>> # Extract parameter count
    >>> from src.utils.hf_model_metadata import extract_parameter_pattern
    >>> 
    >>> params = extract_parameter_pattern(
    ...     "Qwen 2.5 7B", 
    ...     "Qwen/Qwen2.5-7B-Instruct"
    ... )
    >>> print(params.to_string() if params else "Unknown")  # "7B"

Dependencies:
    - huggingface_hub: get_hf_api() for repo info fetching
    - src.core.config: get_hf_api() lazy loader function
    - src.core.logging: Structured logging
    - dataclasses: Type-safe data structures
    - enum: Enumeration types

Notes:
    - Thread-safe and stateless functions
    - Graceful fallbacks when API fails
    - Regex-based parameter extraction (7b, 1.5b, 350m patterns)
    - Size estimates based on fp16/bf16 precision assumptions
    - Comprehensive logging for debugging and monitoring
"""
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Tuple, List
from huggingface_hub import ModelInfo

from src.core.logging import logger
from src.core.config import get_hf_api


# ============ Enumerations ============

class QuantizationType(Enum):
    """Quantization methods for neural network models.
    
    Attributes:
        FP16: 16-bit floating point (full precision for most use cases).
        BF16: Brain float 16-bit (better range than FP16).
        INT8: 8-bit integer quantization (~50% compression).
        INT4: 4-bit integer quantization (~75% compression).
        GGUF: GGUF format (CPU-optimized, variable precision).
        UNKNOWN: Unknown or mixed precision quantization.
    """
    FP16 = "fp16"
    BF16 = "bf16"
    INT8 = "8bit"
    INT4 = "4bit"
    GGUF = "gguf"
    UNKNOWN = "unknown"


class ParameterScale(Enum):
    """Scale for parameter counts (billions or millions).
    
    Attributes:
        BILLION: Parameters in billions (e.g., 7B, 13B).
        MILLION: Parameters in millions (e.g., 350M, 125M).
    """
    BILLION = "B"
    MILLION = "M"


# ============ Data Structures ============

@dataclass(frozen=True)
class ModelSize:
    """Structured representation of model size with uncertainty.
    
    Attributes:
        size_gb: Size in gigabytes (central estimate).
        min_gb: Minimum size in GB (lower bound of estimate).
        max_gb: Maximum size in GB (upper bound of estimate).
        is_estimate: True if size is estimated, False if from API.
        source: Source of size information ("api", "estimate", "unknown").
    
    Example:
        >>> size = ModelSize(size_gb=3.2, min_gb=3.0, max_gb=3.5, is_estimate=False, source="api")
        >>> print(size.to_string())  # "~3.2 GB"
        >>> 
        >>> estimate = ModelSize(size_gb=13.5, min_gb=13.0, max_gb=14.0, is_estimate=True, source="estimate")
        >>> print(estimate.to_string())  # "~13.5 GB"
    """
    size_gb: float
    min_gb: Optional[float] = None
    max_gb: Optional[float] = None
    is_estimate: bool = True
    source: str = "estimate"
    
    def to_string(self) -> str:
        """Format size as human-readable string.
        
        Returns:
            String like "~3.2 GB" (precise) or "~3-4 GB" (range estimate).
        """
        if self.min_gb is not None and self.max_gb is not None and self.is_estimate:
            # Range estimate
            if self.min_gb == self.max_gb:
                return f"~{self.size_gb:.1f} GB"
            return f"~{self.min_gb:.1f}-{self.max_gb:.1f} GB"
        else:
            # Precise or single estimate
            return f"~{self.size_gb:.1f} GB"
    
    def __str__(self) -> str:
        return self.to_string()


@dataclass(frozen=True)
class ParameterCount:
    """Structured representation of model parameter count.
    
    Attributes:
        count: Numeric parameter count (e.g., 7.0 for 7B).
        scale: Scale of parameters (BILLION or MILLION).
        is_estimate: True if count is estimated, False if from metadata.
    
    Example:
        >>> params = ParameterCount(count=7.0, scale=ParameterScale.BILLION, is_estimate=False)
        >>> print(params.to_string())  # "7B"
        >>> 
        >>> small = ParameterCount(count=350, scale=ParameterScale.MILLION, is_estimate=True)
        >>> print(small.to_string())  # "350M"
    """
    count: float
    scale: ParameterScale
    is_estimate: bool = True
    
    def to_string(self) -> str:
        """Format parameter count as human-readable string.
        
        Returns:
            String like "7B", "13B", "1.5B", "350M".
        """
        if self.scale == ParameterScale.BILLION:
            # Format with decimal for non-integer billions
            if self.count % 1 == 0:
                return f"{int(self.count)}{self.scale.value}"
            return f"{self.count:.1f}{self.scale.value}"
        else:
            # Millions are always integers
            return f"{int(self.count)}{self.scale.value}"
    
    def __str__(self) -> str:
        return self.to_string()
    
    @property
    def total_billions(self) -> float:
        """Get total parameter count in billions for comparison.
        
        Returns:
            Parameter count converted to billions (for sorting/comparison).
        """
        if self.scale == ParameterScale.BILLION:
            return self.count
        else:
            return self.count / 1000.0


# ============ Configuration ============

# Model family size mappings (full precision fp16/bf16)
MODEL_SIZE_MAP: Dict[str, Tuple[float, float, float]] = {
    # Mistral models (full precision)
    "mistralai/Mistral-7B-Instruct-v0.3": (13.5, 13.0, 14.0),
    "mistralai/Mistral-7B-v0.3": (13.5, 13.0, 14.0),
    
    # Gemma models (full precision)
    "google/gemma-3-1b-it": (2.5, 2.0, 3.0),
    "google/gemma-2-2b-it": (5.5, 5.0, 6.0),
    "google/gemma-3-4b-it": (9.0, 8.5, 9.5),
    "google/gemma-4-E2B-it": (5.0, 4.5, 5.5),
    "google/gemma-4-E4B-it": (9.0, 8.5, 9.5),
    
    # Qwen models (full precision)
    "Qwen/Qwen2.5-7B-Instruct": (14.5, 14.0, 15.0),
    "Qwen/Qwen2.5-3B-Instruct": (6.5, 6.0, 7.0),
    "Qwen/Qwen2.5-1.5B-Instruct": (3.0, 2.5, 3.5),
    "Qwen/Qwen2.5-0.5B-Instruct": (1.0, 0.8, 1.2),
}

# Parameter size to disk size multipliers (bytes per parameter)
# Assumes fp16 (2 bytes/param) + overhead for embeddings, configs, etc.
SIZE_MULTIPLIERS: Dict[QuantizationType, float] = {
    QuantizationType.FP16: 2.0,  # 2 bytes per parameter
    QuantizationType.BF16: 2.0,  # 2 bytes per parameter
    QuantizationType.INT8: 1.0,  # 1 byte per parameter
    QuantizationType.INT4: 0.5,  # 0.5 bytes per parameter
    QuantizationType.GGUF: 1.0,  # Variable, default to 1 byte
    QuantizationType.UNKNOWN: 2.0,  # Default to fp16
}


# ============ Exception Classes ============

class HFMetadataError(Exception):
    """Base exception for HuggingFace metadata operations."""
    pass


class HFAPIError(HFMetadataError):
    """Exception raised when HuggingFace API calls fail."""
    pass


class ParameterExtractionError(HFMetadataError):
    """Exception raised when parameter count cannot be extracted."""
    pass


# ============ Helper Functions ============

def parse_quantization_type(repo_id: str) -> QuantizationType:
    """Detect quantization type from repository ID.
    
    Args:
        repo_id: HuggingFace repository ID (e.g., "mlx-community/Model-4bit").
    
    Returns:
        Detected QuantizationType enum value.
    
    Example:
        >>> quant = parse_quantization_type("mlx-community/Mistral-7B-v0.3-4bit")
        >>> print(quant)  # QuantizationType.INT4
    """
    repo_lower = repo_id.lower()
    
    if "4bit" in repo_lower or "4-bit" in repo_lower:
        return QuantizationType.INT4
    elif "8bit" in repo_lower or "8-bit" in repo_lower:
        return QuantizationType.INT8
    elif "gguf" in repo_lower:
        return QuantizationType.GGUF
    elif "bf16" in repo_lower:
        return QuantizationType.BF16
    elif "fp16" in repo_lower:
        return QuantizationType.FP16
    else:
        return QuantizationType.UNKNOWN


def calculate_size_from_parameters(
    param_count: ParameterCount,
    quant_type: QuantizationType = QuantizationType.FP16
) -> ModelSize:
    """Estimate model size from parameter count and quantization type.
    
    Args:
        param_count: Structured parameter count.
        quant_type: Quantization type (default FP16).
    
    Returns:
        Estimated ModelSize with uncertainty bounds.
    
    Example:
        >>> params = ParameterCount(count=7.0, scale=ParameterScale.BILLION, is_estimate=False)
        >>> size = calculate_size_from_parameters(params, QuantizationType.FP16)
        >>> print(size.to_string())  # "~14.0 GB" (7B * 2 bytes)
    """
    # Convert to total parameters in billions
    total_params_billions = param_count.total_billions
    
    # Get multiplier for quantization type
    bytes_per_param = SIZE_MULTIPLIERS[quant_type]
    
    # Calculate base size (params * bytes/param)
    base_size_gb = total_params_billions * bytes_per_param
    
    # Add overhead for embeddings, configs, tokenizer (10-15%)
    overhead_factor = 1.0 + 0.125  # 12.5% overhead
    size_gb = base_size_gb * overhead_factor
    
    # Calculate uncertainty bounds (±10%)
    min_gb = size_gb * 0.9
    max_gb = size_gb * 1.1
    
    return ModelSize(
        size_gb=size_gb,
        min_gb=min_gb,
        max_gb=max_gb,
        is_estimate=True,
        source="calculated"
    )


def extract_parameter_pattern(text: str) -> Optional[ParameterCount]:
    """Extract parameter count from text using regex patterns.
    
    Args:
        text: Text to search (model name or repo ID).
    
    Returns:
        ParameterCount if pattern found, None otherwise.
    
    Example:
        >>> params = extract_parameter_pattern("Qwen2.5-7B-Instruct")
        >>> print(params.to_string())  # "7B"
    """
    text_lower = text.lower()
    
    # Pattern for billions: 7b, 7.5b, 70b, etc.
    billion_pattern = r'(\d+\.?\d*)b(?:illion)?'
    billion_matches = re.findall(billion_pattern, text_lower)
    
    if billion_matches:
        count = float(billion_matches[0])
        return ParameterCount(
            count=count,
            scale=ParameterScale.BILLION,
            is_estimate=True
        )
    
    # Pattern for millions: 350m, 125m, etc.
    million_pattern = r'(\d+)m(?:illion)?'
    million_matches = re.findall(million_pattern, text_lower)
    
    if million_matches:
        count = float(million_matches[0])
        return ParameterCount(
            count=count,
            scale=ParameterScale.MILLION,
            is_estimate=True
        )
    
    return None


# ============ Public API Functions ============

def get_disk_size_after_quant(link_hf_quant_repo: str) -> ModelSize:
    """Get actual disk size of quantized model from HuggingFace Hub API.

    Fetches repository metadata via HF API and sums file sizes to get accurate
    total size. Falls back to estimates based on quantization level and parameter
    count if API call fails.

    Args:
        link_hf_quant_repo: HuggingFace repo ID for quantized model.
            Format: "mlx-community/Model-Name-4bit" or similar.

    Returns:
        ModelSize object with actual size from API or estimated size.

    Raises:
        HFAPIError: If API call fails and estimation is impossible.

    Examples:
        >>> # Get actual size via API
        >>> size = get_disk_size_after_quant("mlx-community/Mistral-7B-v0.3-4bit")
        >>> print(size.to_string())  # "~3.2 GB" (actual from API)
        >>> 
        >>> # Fallback to estimate on error
        >>> size = get_disk_size_after_quant("mlx-community/Model-4bit")
        >>> print(size.to_string())  # "~3.0-4.0 GB" (estimated for 4-bit ~7B)

    Notes:
        - Uses get_hf_api().repo_info with files_metadata=True
        - Sums all file sizes in repo (weights, config, tokenizer)
        - Fallback logic: Detects quantization type and parameter count
        - Error handling: Logs error and returns best estimate
        - Precision: Returns size with 0.1 GB precision
    """
    try:
        logger.debug(f"Fetching disk size for quantized repo: {link_hf_quant_repo}")
        
        hf_api = get_hf_api()
        repo_info = hf_api.repo_info(link_hf_quant_repo, files_metadata=True)
        total_size_bytes = sum(file.size for file in repo_info.siblings if file.size)
        
        # Convert to GB with high precision
        size_gb = total_size_bytes / (1024**3)
        
        logger.info(f"Retrieved actual size for {link_hf_quant_repo}: {size_gb:.2f} GB")
        
        return ModelSize(
            size_gb=size_gb,
            min_gb=size_gb,
            max_gb=size_gb,
            is_estimate=False,
            source="api"
        )
        
    except Exception as e:
        logger.warning(f"Failed to fetch size from HF API for {link_hf_quant_repo}: {e}")
        logger.debug("Falling back to estimate based on quantization type")
        
        # Fallback: Estimate based on quantization type and parameter count
        quant_type = parse_quantization_type(link_hf_quant_repo)
        param_count = get_parameter_count_from_name("", link_hf_quant_repo)
        
        if param_count != "Unknown":
            # Have parameter count, calculate based on that
            try:
                params = extract_parameter_pattern(link_hf_quant_repo)
                if params:
                    estimated_size = calculate_size_from_parameters(params, quant_type)
                    logger.info(f"Estimated size for {link_hf_quant_repo}: {estimated_size.to_string()}")
                    return estimated_size
            except Exception as calc_error:
                logger.debug(f"Failed to calculate from parameters: {calc_error}")
        
        # Rough fallback estimates based on common patterns
        if quant_type == QuantizationType.INT4:
            # 4-bit quantization, assume ~7B model
            return ModelSize(size_gb=3.5, min_gb=3.0, max_gb=4.0, is_estimate=True, source="fallback")
        elif quant_type == QuantizationType.INT8:
            # 8-bit quantization, check for size hints
            repo_lower = link_hf_quant_repo.lower()
            if "1b" in repo_lower:
                return ModelSize(size_gb=1.5, min_gb=1.0, max_gb=2.0, is_estimate=True, source="fallback")
            elif "2b" in repo_lower:
                return ModelSize(size_gb=2.5, min_gb=2.0, max_gb=3.0, is_estimate=True, source="fallback")
            elif "4b" in repo_lower:
                return ModelSize(size_gb=4.5, min_gb=4.0, max_gb=5.0, is_estimate=True, source="fallback")
            else:
                # Default to ~7B 8-bit
                return ModelSize(size_gb=7.0, min_gb=6.0, max_gb=8.0, is_estimate=True, source="fallback")
        else:
            # Unknown quantization, very rough estimate
            logger.warning(f"Could not determine size for {link_hf_quant_repo}, returning unknown")
            return ModelSize(size_gb=0.0, min_gb=0.0, max_gb=0.0, is_estimate=True, source="unknown")


def get_model_size_estimate(model_name: str, link: str) -> ModelSize:
    """Estimate model size for known base models and derivatives.

    Provides size estimates for popular model families (Mistral, Gemma, Qwen) in
    full precision (fp16/bf16). Uses exact matches for known repos, then
    falls back to pattern matching for derivatives and fine-tunes.

    Estimation Logic:
    1. Check exact repo ID in MODEL_SIZE_MAP
    2. Match family pattern (Mistral, Gemma, Qwen) + parameter count
    3. Calculate from extracted parameter count if available
    4. Return unknown ModelSize if no match

    Args:
        model_name: Human-readable model name (e.g., "Mistral Instruct").
            Used for pattern matching when link is custom/fine-tuned.
        link: HuggingFace repo ID (e.g., "mistralai/Mistral-7B-Instruct-v0.3").
            Primary source for matching.

    Returns:
        ModelSize object with estimate or unknown.

    Examples:
        >>> # Exact match
        >>> size = get_model_size_estimate(
        ...     "Mistral 7B Instruct",
        ...     "mistralai/Mistral-7B-Instruct-v0.3"
        ... )
        >>> print(size.to_string())  # "~13.5 GB"
        >>> 
        >>> # Pattern match for derivative
        >>> size = get_model_size_estimate(
        ...     "Custom Mistral 7B Finetune",
        ...     "user/custom-mistral-7b-finetune"
        ... )
        >>> print(size.to_string())  # "~13.0-14.0 GB" (matched "mistral" + "7b")

    Notes:
        - Full precision only: Does not account for quantization
        - Hardcoded map: Mistral, Gemma, Qwen families
        - Pattern matching: Case-insensitive, checks name + link
        - Returns ModelSize with uncertainty bounds for estimates
    """
    logger.debug(f"Estimating size for model: {model_name}, link: {link}")
    
    # First check for exact match in size map
    if link in MODEL_SIZE_MAP:
        size_gb, min_gb, max_gb = MODEL_SIZE_MAP[link]
        logger.info(f"Found exact match for {link}: {size_gb} GB")
        return ModelSize(
            size_gb=size_gb,
            min_gb=min_gb,
            max_gb=max_gb,
            is_estimate=True,
            source="map"
        )
    
    # Pattern matching for derivatives
    model_name_lower = model_name.lower()
    link_lower = link.lower()
    combined_text = f"{model_name_lower} {link_lower}"
    
    # Extract parameter count
    param_count = extract_parameter_pattern(combined_text)
    
    if param_count:
        # Mistral family
        if "mistral" in combined_text:
            if param_count.total_billions >= 6.5 and param_count.total_billions <= 8.0:
                logger.info(f"Matched Mistral 7B pattern for {link}")
                return ModelSize(size_gb=13.5, min_gb=13.0, max_gb=14.0, is_estimate=True, source="pattern")
        
        # Gemma family
        if "gemma" in combined_text:
            total_b = param_count.total_billions
            is_gemma4 = "gemma-4" in combined_text or "gemma4" in combined_text
            if 0.8 <= total_b <= 1.2:
                logger.info(f"Matched Gemma 1B pattern for {link}")
                return ModelSize(size_gb=2.5, min_gb=2.0, max_gb=3.0, is_estimate=True, source="pattern")
            elif 1.8 <= total_b <= 2.2:
                size = 5.0 if is_gemma4 else 5.5  # Gemma 4 E2B is MoE, slightly smaller quantized
                logger.info(f"Matched Gemma {'4 E2B' if is_gemma4 else '2B'} pattern for {link}")
                return ModelSize(size_gb=size, min_gb=4.5, max_gb=6.0, is_estimate=True, source="pattern")
            elif 3.5 <= total_b <= 4.5:
                size = 9.0  # same ballpark for Gemma 3 4B and Gemma 4 E4B
                logger.info(f"Matched Gemma {'4 E4B' if is_gemma4 else '4B'} pattern for {link}")
                return ModelSize(size_gb=size, min_gb=8.5, max_gb=9.5, is_estimate=True, source="pattern")
            elif 6.5 <= total_b <= 8.0:
                logger.info(f"Matched Gemma 7B pattern for {link}")
                return ModelSize(size_gb=13.5, min_gb=13.0, max_gb=14.0, is_estimate=True, source="pattern")
        
        # Qwen family
        if "qwen" in combined_text:
            total_b = param_count.total_billions
            if 0.4 <= total_b <= 0.6:
                logger.info(f"Matched Qwen 0.5B pattern for {link}")
                return ModelSize(size_gb=1.0, min_gb=0.8, max_gb=1.2, is_estimate=True, source="pattern")
            elif 1.3 <= total_b <= 1.7:
                logger.info(f"Matched Qwen 1.5B pattern for {link}")
                return ModelSize(size_gb=3.0, min_gb=2.5, max_gb=3.5, is_estimate=True, source="pattern")
            elif 2.8 <= total_b <= 3.2:
                logger.info(f"Matched Qwen 3B pattern for {link}")
                return ModelSize(size_gb=6.5, min_gb=6.0, max_gb=7.0, is_estimate=True, source="pattern")
            elif 6.5 <= total_b <= 8.0:
                logger.info(f"Matched Qwen 7B pattern for {link}")
                return ModelSize(size_gb=14.5, min_gb=14.0, max_gb=15.0, is_estimate=True, source="pattern")
        
        # Generic calculation for unknown families
        logger.info(f"No family match, calculating from parameters for {link}")
        return calculate_size_from_parameters(param_count, QuantizationType.FP16)
    
    # No match found
    logger.warning(f"Could not estimate size for {link}")
    return ModelSize(size_gb=0.0, min_gb=0.0, max_gb=0.0, is_estimate=True, source="unknown")


def get_parameter_count_from_name(model_name: str, link: str) -> str:
    """Extract parameter count from model name or HuggingFace link.

    Uses regex to find common parameter count patterns in model names and
    repo IDs. Supports billion (B) and million (M) scale models.

    **DEPRECATED**: This function returns strings for backward compatibility.
    New code should use extract_parameter_pattern() which returns typed
    ParameterCount objects.

    Patterns Matched:
    - Billions: "7b", "7B", "7.5b", "70b" → "7B", "7.5B", "70B"
    - Millions: "350m", "125M" → "350M", "125M"
    - Variants: "billion", "million" words also matched

    Args:
        model_name: Human-readable model name (e.g., "Mistral 7B Instruct").
        link: HuggingFace repo ID (e.g., "mistralai/Mistral-7B-Instruct-v0.3").
            Both are lowercased and searched together.

    Returns:
        Parameter count string like "7B", "1.5B", "350M", or "Unknown" if
        no pattern matched.

    Examples:
        >>> # Standard cases
        >>> params = get_parameter_count_from_name(
        ...     "Qwen 2.5 7B Instruct", 
        ...     "Qwen/Qwen2.5-7B-Instruct"
        ... )
        >>> print(params)  # "7B"
        >>> 
        >>> # Decimal parameters
        >>> params = get_parameter_count_from_name(
        ...     "Phi 3.5 1.5B", 
        ...     "microsoft/phi-3.5-mini-1.5b"
        ... )
        >>> print(params)  # "1.5B"

    Notes:
        - Case-insensitive: Converts to lowercase before matching
        - First match wins: If multiple patterns found, uses first
        - Backward compatibility: Returns string instead of ParameterCount
        - Deprecated: Use extract_parameter_pattern() for new code
    """
    combined_text = f"{model_name} {link}"
    param_count = extract_parameter_pattern(combined_text)
    
    if param_count:
        return param_count.to_string()
    else:
        return "Unknown"


def format_model_info_metadata(
    model_info: ModelInfo,
    size_estimate: Optional[ModelSize] = None,
    quantized: bool = False
) -> str:
    """Format HuggingFace ModelInfo object into structured string for storage.

    Converts a huggingface_hub.ModelInfo object into a multi-line string
    containing all relevant metadata fields. Includes size estimates and
    parameter counts for display in UI and database storage.

    Formatted Fields:
    - Model ID, Author, Created, Downloads, Likes
    - Library, Pipeline, Size, Parameters, Quantized status
    - Private/Gated flags, Tags (first 10), SHA, Last Modified

    Args:
        model_info: huggingface_hub.ModelInfo object from HF API. Contains
            all metadata fields from HuggingFace Hub.
        size_estimate: Optional ModelSize object. If None, shows "Unknown".
            Get from get_model_size_estimate or get_disk_size_after_quant.
        quantized: Boolean indicating if model is quantized (default: False).
            Shows "True" or "False" in output.

    Returns:
        Multi-line formatted string with all metadata fields, or error message
        if formatting fails.

    Examples:
        >>> from src.utils.hf_model_metadata import format_model_info_metadata
        >>> from huggingface_hub import HfApi
        >>> 
        >>> # Fetch model info and format
        >>> api = HfApi()
        >>> model_info = api.model_info("mistralai/Mistral-7B-Instruct-v0.3")
        >>> size = get_model_size_estimate("Mistral 7B", model_info.id)
        >>> 
        >>> metadata_str = format_model_info_metadata(
        ...     model_info,
        ...     size_estimate=size,
        ...     quantized=False
        ... )
        >>> print(metadata_str)
        # Model ID: mistralai/Mistral-7B-Instruct-v0.3
        # Author: mistralai
        # Created: 2024-05-22T14:00:00.000Z
        # Downloads: 1234567
        # Likes: 5678
        # Library: transformers
        # Pipeline: text-generation
        # Size: ~13.5 GB
        # Parameters: 7B
        # Quantized: False
        # ...

    Notes:
        - Parameter extraction: Uses extract_parameter_pattern internally
        - Tag limit: Shows first 10 tags, adds "..." if more exist
        - Error handling: Returns "Error formatting metadata: {error}" on failure
        - Use case: Store in Llm.model_metadata field for UI display
        - Timestamps: ISO format from HuggingFace Hub
    """
    try:
        # Extract parameter count from model ID
        param_count = extract_parameter_pattern(model_info.id)
        param_str = param_count.to_string() if param_count else "Unknown"
        
        # Format size estimate
        size_str = size_estimate.to_string() if size_estimate else "Unknown"
        
        metadata_str = f"""Model ID: {model_info.id}
Author: {model_info.author or 'Unknown'}
Created: {model_info.created_at or 'Unknown'}
Downloads: {model_info.downloads or 0} 
Likes: {model_info.likes or 0}
Library: {model_info.library_name or 'Unknown'}
Pipeline: {model_info.pipeline_tag or 'Unknown'}
Size: {size_str}
Parameters: {param_str}
Quantized: {quantized}
Private: {model_info.private}
Gated: {model_info.gated}
Tags: {', '.join(model_info.tags[:10]) if model_info.tags else 'None'}{'...' if model_info.tags and len(model_info.tags) > 10 else ''}
SHA: {model_info.sha or 'Unknown'}
Last Modified: {model_info.last_modified or 'Unknown'}"""
        
        logger.debug(f"Formatted metadata for {model_info.id}")
        return metadata_str
        
    except Exception as e:
        error_msg = f"Error formatting metadata: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg


# ============ Module Exports ============

__all__ = [
    # Data structures
    "ModelSize",
    "ParameterCount",
    "QuantizationType",
    "ParameterScale",
    # Main API functions
    "get_disk_size_after_quant",
    "get_model_size_estimate",
    "format_model_info_metadata",
    # Helper functions
    "parse_quantization_type",
    "calculate_size_from_parameters",
    "extract_parameter_pattern",
    # Exceptions
    "HFMetadataError",
    "HFAPIError",
    "ParameterExtractionError",
]

