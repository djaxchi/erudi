"""HuggingFace Model Metadata Utilities.

This module provides functions for fetching and formatting model metadata from
HuggingFace Hub, including size estimation, parameter count extraction, and
structured metadata formatting for database storage.

Key Features:
    - Calculate actual disk size for quantized MLX models via HF API
    - Estimate sizes for known base models (Mistral, Gemma families)
    - Extract parameter counts from model names/links (7B, 1B, etc.)
    - Format ModelInfo objects into structured strings for storage

Functions:
    get_disk_size_after_quant: Get actual size of MLX quantized repo.
    get_model_size_estimate: Estimate size for known base models.
    get_parameter_count_from_name: Extract parameter count from naming.
    format_model_info_metadata: Format ModelInfo to structured string.

Size Estimates:
    - Mistral-7B (full precision): ~13.5 GB
    - Gemma-1B (full precision): ~2.5 GB
    - Gemma-2B (full precision): ~5.5 GB
    - Gemma-4B (full precision): ~9.0 GB
    - MLX 4-bit quantized 7B: ~3-4 GB
    - MLX 8-bit quantized 1B/2B/4B: ~1-2 GB / ~2-3 GB / ~4-5 GB

Examples:
    >>> # Get actual size of MLX quantized model
    >>> from src.utils.hf_model_metadata import get_disk_size_after_quant
    >>> 
    >>> size = get_disk_size_after_quant("mlx-community/Mistral-7B-v0.3-4bit")
    >>> print(size)  # "~3.2 GB" (actual from API)
    >>> 
    >>> # Estimate size for base model
    >>> from src.utils.hf_model_metadata import get_model_size_estimate
    >>> 
    >>> size = get_model_size_estimate(
    ...     "Mistral Instruct", 
    ...     "mistralai/Mistral-7B-Instruct-v0.3"
    ... )
    >>> print(size)  # "~13.5 GB"
    >>> 
    >>> # Extract parameter count
    >>> from src.utils.hf_model_metadata import get_parameter_count_from_name
    >>> 
    >>> params = get_parameter_count_from_name(
    ...     "Qwen 2.5 7B", 
    ...     "Qwen/Qwen2.5-7B-Instruct"
    ... )
    >>> print(params)  # "7B"

Dependencies:
    - huggingface_hub: HF_API for repo info fetching
    - src.core.config: HF_API singleton instance

Notes:
    - Fallback estimates when API fails or model unknown
    - Regex-based parameter extraction (7b, 1.5b, 350m patterns)
    - Size estimates based on fp16/bf16 precision assumptions
"""
from src.core.logging import logger
from src.core.config import HF_API

def get_disk_size_after_quant(link_hf_quant_repo):
    """Get actual disk size of MLX quantized model from HuggingFace Hub.

    Fetches repo metadata via HF API and sums file sizes to get accurate
    total size. Falls back to estimates based on quantization level if
    API call fails.

    Args:
        link_hf_quant_repo: HuggingFace repo ID for quantized model.
            Format: "mlx-community/Model-Name-4bit" or similar.

    Returns:
        Size string like "~3.2 GB" (actual from API) or "~3-4 GB" (estimate).
        Returns "Unknown" if estimation impossible.

    Examples:
        >>> from src.utils.hf_model_metadata import get_disk_size_after_quant
        >>> 
        >>> # Get actual size via API
        >>> size = get_disk_size_after_quant("mlx-community/Mistral-7B-v0.3-4bit")
        >>> print(size)  # "~3.2 GB" (actual)
        >>> 
        >>> # Fallback to estimate on error
        >>> size = get_disk_size_after_quant("invalid/repo-4bit")
        >>> print(size)  # "~3-4 GB" (estimate for 4-bit)

    Notes:
        - Uses HF_API.repo_info with files_metadata=True
        - Sums all file sizes in repo (weights, config, tokenizer)
        - Fallback estimates: 4-bit ~3-4 GB, 8-bit ~1-5 GB depending on size
        - Error handling: Logs error and returns estimate or "Unknown"
        - Precision: Converts bytes to GB with 1 decimal place

    Raises:
        Does not raise - catches all exceptions and returns estimate/unknown.

    See Also:
        get_model_size_estimate: Estimates for non-quantized models
    """
    try:
        repo_info = HF_API.repo_info(link_hf_quant_repo, files_metadata=True)
        total_size = sum(file.size for file in repo_info.siblings if file.size)
        # Convert to GB
        size_gb = total_size / (1024**3)
        return f"~{size_gb:.1f} GB"
    except Exception as e:
        logger.error(f"Error getting MLX model size for {link_hf_quant_repo}: {e}")
        # Fallback estimates based on quantization
        if "4bit" in link_hf_quant_repo.lower():
            return "~3-4 GB"  # Rough estimate for 4-bit 7B models
        elif "8bit" in link_hf_quant_repo.lower():
            if "1b" in link_hf_quant_repo.lower():
                return "~1-2 GB"
            elif "2b" in link_hf_quant_repo.lower():
                return "~2-3 GB"
            elif "4b" in link_hf_quant_repo.lower():
                return "~4-5 GB"
        return "Unknown"

def get_model_size_estimate(model_name, link):
    """Estimate model size for known base models and derivatives.

    Provides size estimates for popular model families (Mistral, Gemma) in
    full precision (fp16/bf16). Uses exact matches for known repos, then
    falls back to pattern matching for derivatives and fine-tunes.

    Estimation Logic:
    1. Check exact repo ID in hardcoded SIZE_MAP
    2. Match Mistral-7B pattern → 13.5 GB
    3. Match Gemma family by parameter count (1B/2B/4B/7B)
    4. Return "Unknown" if no match

    Args:
        model_name: Human-readable model name (e.g., "Mistral Instruct").
            Used for pattern matching when link is custom/fine-tuned.
        link: HuggingFace repo ID (e.g., "mistralai/Mistral-7B-Instruct-v0.3").
            Primary source for matching.

    Returns:
        Size estimate string like "~13.5 GB" or "Unknown" if not recognized.
        Assumes full precision (fp16/bf16), not quantized.

    Examples:
        >>> from src.utils.hf_model_metadata import get_model_size_estimate
        >>> 
        >>> # Exact match
        >>> size = get_model_size_estimate(
        ...     "Mistral 7B Instruct",
        ...     "mistralai/Mistral-7B-Instruct-v0.3"
        ... )
        >>> print(size)  # "~13.5 GB"
        >>> 
        >>> # Pattern match for derivative
        >>> size = get_model_size_estimate(
        ...     "Custom Mistral 7B Finetune",
        ...     "user/custom-mistral-7b-finetune"
        ... )
        >>> print(size)  # "~13.5 GB" (matched "mistral" + "7b")
        >>> 
        >>> # Unknown model
        >>> size = get_model_size_estimate("Unknown Model", "user/unknown")
        >>> print(size)  # "Unknown"

    Notes:
        - Full precision only: Does not account for quantization
        - Hardcoded map: Mistral-7B, Gemma-1B/2B/4B
        - Pattern matching: Case-insensitive, checks name + link
        - Gemma sizes: 1B=~2.5GB, 2B=~5.5GB, 4B=~9GB, 7B=~13.5GB
        - Approximations: Based on typical fp16 weight sizes

    See Also:
        get_disk_size_after_quant: For quantized MLX model sizes
        get_parameter_count_from_name: Extract param count for better matching
    """
    # Global size map for model size estimates
    SIZE_MAP = {
        # Mistral models (full precision)
        "mistralai/Mistral-7B-Instruct-v0.3": "~13.5 GB",
        "mistralai/Mistral-7B-v0.3": "~13.5 GB",
        # Gemma models (full precision)
        "google/gemma-3-1b-it": "~2.5 GB",
        "google/gemma-2-2b-it": "~5.5 GB", 
        "google/gemma-3-4b-it": "~9.0 GB",
    }

    # First check for exact match
    if link in SIZE_MAP:
        return SIZE_MAP[link]
    
    # Check for derived models based on model name patterns
    model_name_lower = model_name.lower()
    link_lower = link.lower()
    
    # Mistral 7B derivatives
    if ("mistral" in model_name_lower and ("7b" in model_name_lower or "7b" in link_lower)):
        return "~13.5 GB"
    
    # Gemma derivatives based on parameter count
    if "gemma" in model_name_lower or "gemma" in link_lower:
        if "1b" in model_name_lower or "1b" in link_lower:
            return "~2.5 GB"
        elif "2b" in model_name_lower or "2b" in link_lower:
            return "~5.5 GB"
        elif "4b" in model_name_lower or "4b" in link_lower:
            return "~9.0 GB"
        elif "7b" in model_name_lower or "7b" in link_lower:
            return "~13.5 GB"
    
    return "Unknown"

def get_parameter_count_from_name(model_name, link):
    """Extract parameter count from model name or HuggingFace link.

    Uses regex to find common parameter count patterns in model names and
    repo IDs. Supports billion (B) and million (M) scale models.

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
        >>> from src.utils.hf_model_metadata import get_parameter_count_from_name
        >>> 
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
        >>> 
        >>> # Million-scale model
        >>> params = get_parameter_count_from_name(
        ...     "GPT-2 Small", 
        ...     "openai/gpt2-small-125m"
        ... )
        >>> print(params)  # "125M"
        >>> 
        >>> # Unknown
        >>> params = get_parameter_count_from_name("Unknown", "user/model")
        >>> print(params)  # "Unknown"

    Notes:
        - Case-insensitive: Converts to lowercase before matching
        - First match wins: If multiple patterns found, uses first
        - Decimal support: "7.5b" → "7.5B"
        - Billion vs Million: Automatically formats with B or M suffix
        - Combined search: Searches both name and link together

    See Also:
        get_model_size_estimate: Uses this for better size estimation
        format_model_info_metadata: Includes parameter count in output
    """
    import re
    
    # Combine name and link for searching
    search_text = f"{model_name} {link}".lower()
    
    # Look for common parameter patterns
    # Match patterns like: 7b, 7B, 70b, 13b, 1.5b, etc.
    param_patterns = [
        r'(\d+\.?\d*)b(?:illion)?',  # 7b, 7.5b, 70b
        r'(\d+\.?\d*)m(?:illion)?',  # 350m, 125m
    ]
    
    for pattern in param_patterns:
        matches = re.findall(pattern, search_text)
        if matches:
            param_value = float(matches[0])
            if 'b' in pattern:
                return f"{param_value}B"
            else:  # million
                return f"{int(param_value)}M"
    
    return "Unknown"

def format_model_info_metadata(model_info, size_estimate=None, quantized=False):
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
        size_estimate: Optional size string (e.g., "~13.5 GB"). If None,
            shows "Unknown". Get from get_model_size_estimate or
            get_disk_size_after_quant.
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
        >>> 
        >>> metadata_str = format_model_info_metadata(
        ...     model_info,
        ...     size_estimate="~13.5 GB",
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
        # Private: False
        # Gated: False
        # Tags: llm, mistral, instruct, ...
        # SHA: abc123def456...
        # Last Modified: 2024-05-23T10:00:00.000Z

    Notes:
        - Parameter extraction: Uses get_parameter_count_from_name internally
        - Tag limit: Shows first 10 tags, adds "..." if more exist
        - Error handling: Returns "Error formatting metadata: {error}" on failure
        - Use case: Store in Llm.metadata_json field for UI display
        - Timestamps: ISO format from HuggingFace Hub

    See Also:
        get_model_size_estimate: Get size_estimate parameter
        get_disk_size_after_quant: Get size_estimate for quantized models
        get_parameter_count_from_name: Extract parameter count
    """
    try:
        # Extract parameter count from model name
        param_count = get_parameter_count_from_name(model_info.id, model_info.id)
        
        metadata_str = f"""Model ID: {model_info.id}
Author: {model_info.author}
Created: {model_info.created_at}
Downloads: {model_info.downloads} 
Likes: {model_info.likes}
Library: {model_info.library_name}
Pipeline: {model_info.pipeline_tag}
Size: {size_estimate or 'Unknown'}
Parameters: {param_count}
Quantized: {quantized}
Private: {model_info.private}
Gated: {model_info.gated}
Tags: {', '.join(model_info.tags[:10]) if model_info.tags else 'None'}{'...' if model_info.tags and len(model_info.tags) > 10 else ''}
SHA: {model_info.sha}
Last Modified: {model_info.last_modified}"""
        return metadata_str
    except Exception as e:
        return f"Error formatting metadata: {str(e)}"

