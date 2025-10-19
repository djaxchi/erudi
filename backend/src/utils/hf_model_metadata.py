from src.core.logging import logger
from src.core.vars import HF_API

def get_disk_size_after_quant(link_hf_quant_repo):
    """Get the actual size of MLX quantized model from Hugging Face"""
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
    """Get approximate model size for known base models and their derivatives"""
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
    """Extract parameter count from model name or link"""
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
    """Format ModelInfo object into a structured string for storage"""
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

