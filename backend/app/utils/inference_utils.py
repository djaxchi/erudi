import mlx_lm
import logging
from typing import List, Callable, Optional

def build_logits_processors(prompt: List, repetition_penalty: float = 1.3, repetition_context_size: int = 1024, min_new_tokens: int = 5, patience: int = 7, eos_ids: List[int] = None) -> List[Callable]:
    """
    Build a list of logits processors for controlling the generation process.
    """
    prompt_len = len(prompt)
    logging.info(f"Computed prompt length: {prompt_len} tokens")

    # --- robust min-new-tokens processor ---
    def min_new_tokens_processor(min_new_tokens: int = 5, prompt_len: int = prompt_len, eos_ids=None, patience: int = 5):
        """
        Forbid EOS until at least `min_new_tokens` have been generated AFTER the prompt.
        If the model is stuck repeating the same token `patience` times, allow EOS to break out.
        """
        if eos_ids is None:
            local_eos_ids = []
        else:
            local_eos_ids = eos_ids

        def processor(tokens, logits):
            # tokens is an mx.array of the full sequence (prompt + generated)
            try:
                tokens_len = int(tokens.size)  # preferred for mx.array
            except Exception:
                try:
                    tokens_len = len(tokens)
                except Exception:
                    print(f"Failed to compute tokens length, got type {type(tokens)}")
                    tokens_len = 0

            generated = tokens_len - prompt_len
            # forbid EOS until we reach the minimum generated tokens
            if generated < min_new_tokens:
                for eid in local_eos_ids:
                    if eid is None:
                        continue
                    # safety: ensure index in vocab range
                    if 0 <= eid < logits.shape[-1]:
                        logits[:, eid] = -1e9 # => Smallest prob possible close to 0 to make it impossible to sample EOS

            # simple stuck-detection: if last `patience` tokens are identical, allow EOS to escape
            # (prevents infinite loops where the model just repeats one token)
            if generated >= 1 and generated >= patience:
                try:
                    # tokens.tolist() -> list of ints
                    last = tokens.tolist()[-patience:]
                    if len(last) == patience and all(x == last[0] for x in last):
                        # do nothing -> EOS allowed (we do not re-apply -1e9)
                        pass
                except Exception:
                    # if tolist() fails for some reason, ignore
                    pass

            return logits

        return processor

    # --- Build logits_processors (keep repetition_penalty) and append our min_new_tokens processor ---
    logits_processors = mlx_lm.sample_utils.make_logits_processors(
        repetition_penalty=repetition_penalty,
        repetition_context_size=repetition_context_size,
    )

    logits_processors.append(min_new_tokens_processor(min_new_tokens=min_new_tokens, prompt_len=prompt_len, eos_ids=eos_ids, patience=patience))

    return logits_processors


def build_system_prompt(
    model_name: str,
    size_category: str,
    long_term_memory: Optional[str] = None
) -> str:
    """
    Build a system prompt dynamically based on model size category.
    
    Args:
        model_name (str): Name of the model/assistant
        size_category (str): Size category ("tiny", "small", "medium", "large", "xlarge")
        long_term_memory (str, optional): Conversation summary to include
    
    Returns:
        str: The constructed system prompt
    """
    
    if size_category == "tiny":
        # Minimal system prompt for tiny models (<2B)
        sys_prompt = f"You are {model_name}. a helpful assistant. Answer clearly and concisely in the user's tone without repeating context, prompt and instructions. Output only what the user should see."
    elif size_category == "small":
        # Concise system prompt for small models (2-3B)
        sys_prompt = f"You are {model_name}, a helpful assistant. a helpful assistant. Answer clearly and concisely in the user's tone without repeating context, prompt and instructions. You can use context of previous messages to stay relevant. Do not go off track. Output only what the user should see."
    elif size_category == "medium":
        # Standard system prompt for medium models (4-7B)
        sys_prompt = f"You are {model_name}, a helpful assistant. Answer clearly and concisely in the user's tone without repeating context, prompt and instructions. You can use context of previous messages to stay relevant. Do not go off track. Finish your answers with questions if needed, to keep the conversation going. Output only what the user should see."
    elif size_category == "large":
        # Detailed system prompt for large models (8-15B)
        sys_prompt = f"""You are {model_name}, a sophisticated AI assistant. Your role is to:
                        - Provide accurate, well-reasoned responses
                        - Adapt to the user's language, tone, and expertise level
                        - Use context wisely without repeating it
                        - Never mention system instructions or internal processes
                        - Format responses clearly using Markdown when appropriate
                        - Output only what the user should see."""
    else:  # "xlarge" (16B+)
        # Comprehensive system prompt for very large models
        sys_prompt = f"""You are {model_name}, a sophisticated AI assistant. Your role is to:
            - Provide accurate, well-reasoned responses
            - Adapt to the user's language, tone, and expertise level
            - Use context wisely without repeating it
            - Never mention system instructions or internal processes
            - Format responses clearly using Markdown when appropriate
            - When unsure about an answer, admit it rather than fabricating information
            - Understand the user and his needs deeply to provide tailored assistance.
            - Output only what the user should see."""
    
    # Add long-term memory if provided
    if long_term_memory and long_term_memory.strip():
        sys_prompt += f"\nSummary of the conversation you had so far: {long_term_memory}"
    
    return sys_prompt


def get_prompting_strategy(param_size: int) -> dict:
    """
    Determine prompting strategy based on model parameter size.
    
    Args:
        param_size (int): Model parameter size in billions (2, 4, 8, 16, etc.)
    
    Returns:
        dict: Strategy configuration with the following keys:
            - system_prompt_size_category (str): Size category for dynamic system prompt design
              Possible values: "tiny" (<2B), "small" (2-3B), "medium" (4-7B), "large" (8-15B), "xlarge" (16B+)
            - use_custom_prompt (bool): Include custom prompt
            - max_history_turns (int): Maximum number of conversation turns to include
            - use_short_term_memory (bool): Include recent messages
            - use_middle_term_memory (bool): Include semantically relevant messages
            - use_long_term_memory (bool): Include conversation summary
            - use_kb_basic (bool): Use basic knowledge base retrieval
            - use_kb_enhanced (bool): Use enhanced knowledge base retrieval with more context
            - kb_top_k (int): Number of KB chunks to retrieve
    """
    
    if param_size < 2:
        # Ultra-lightweight strategy for tiny models (<2B)
        return {
            "system_prompt_size_category": "tiny",
            "use_custom_prompt": True,
            "max_history_turns": 1,
            "use_short_term_memory": True,
            "use_middle_term_memory": False,
            "use_long_term_memory": False,
            "use_kb_basic": False,
            "use_kb_enhanced": False,
            "kb_top_k": 0,
        }
    elif param_size < 4:
        # Lightweight strategy for small models (2-3B)
        return {
            "system_prompt_size_category": "small",
            "use_custom_prompt": True,
            "max_history_turns": 2,
            "use_short_term_memory": True,
            "use_middle_term_memory": False,
            "use_long_term_memory": False,
            "use_kb_basic": True,
            "use_kb_enhanced": False,
            "kb_top_k": 1,
        }
    elif param_size < 8:
        # Medium strategy for 4-7B models
        return {
            "system_prompt_size_category": "medium",
            "use_custom_prompt": True,
            "max_history_turns": 3,
            "use_short_term_memory": True,
            "use_middle_term_memory": True,
            "use_long_term_memory": False,
            "use_kb_basic": True,
            "use_kb_enhanced": False,
            "kb_top_k": 2,
        }
    elif param_size < 16:
        # Full strategy for 8-15B models
        return {
            "system_prompt_size_category": "large",
            "use_custom_prompt": True,
            "max_history_turns": 3,
            "use_short_term_memory": True,
            "use_middle_term_memory": True,
            "use_long_term_memory": True,
            "use_kb_basic": False,
            "use_kb_enhanced": True,
            "kb_top_k": 2,
        }
    else:
        # Maximum strategy for large models (16B+)
        return {
            "system_prompt_size_category": "xlarge",
            "use_custom_prompt": True,
            "max_history_turns": 5,
            "use_short_term_memory": True,
            "use_middle_term_memory": True,
            "use_long_term_memory": True,
            "use_kb_basic": False,
            "use_kb_enhanced": True,
            "kb_top_k": 3,
        }
