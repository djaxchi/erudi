import mlx_lm
import logging
from typing import List, Callable

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


def get_prompting_strategy(param_size: int) -> dict:
    """
    Determine prompting strategy based on model parameter size.
    
    Args:
        param_size (int): Model parameter size in billions (2, 4, 8, 16, etc.)
    
    Returns:
        dict: Strategy configuration with the following keys:
            - use_system_prompt (bool): Include system prompt
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
            "use_system_prompt": True,
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
            "use_system_prompt": True,
            "use_custom_prompt": True,
            "max_history_turns": 1,
            "use_short_term_memory": True,
            "use_middle_term_memory": False,
            "use_long_term_memory": False,
            "use_kb_basic": False,
            "use_kb_enhanced": False,
            "kb_top_k": 0,
        }
    elif param_size < 8:
        # Medium strategy for 4-7B models
        return {
            "use_system_prompt": True,
            "use_custom_prompt": True,
            "max_history_turns": 2,
            "use_short_term_memory": True,
            "use_middle_term_memory": False,
            "use_long_term_memory": False,
            "use_kb_basic": True,
            "use_kb_enhanced": False,
            "kb_top_k": 2,
        }
    elif param_size < 16:
        # Full strategy for 8-15B models
        return {
            "use_system_prompt": True,
            "use_custom_prompt": True,
            "max_history_turns": 3,
            "use_short_term_memory": True,
            "use_middle_term_memory": True,
            "use_long_term_memory": True,
            "use_kb_basic": False,
            "use_kb_enhanced": True,
            "kb_top_k": 3,
        }
    else:
        # Maximum strategy for large models (16B+)
        return {
            "use_system_prompt": True,
            "use_custom_prompt": True,
            "max_history_turns": 5,
            "use_short_term_memory": True,
            "use_middle_term_memory": True,
            "use_long_term_memory": True,
            "use_kb_basic": False,
            "use_kb_enhanced": True,
            "kb_top_k": 5,
        }
