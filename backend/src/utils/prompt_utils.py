"""
Prompt building utilities shared across domains.
"""
from datetime import datetime
from typing import List, Optional

from src.core.logging import logger


def build_system_prompt(
    model_name: str,
    size_category: str,
    long_term_memory: Optional[str] = None,
    starred_messages: Optional[List[str]] = None
) -> str:
    """
    Build a system prompt dynamically based on model size category.
    
    Args:
        model_name: Name of the model/assistant
        size_category: Size category ("tiny", "small", "medium", "large", "xlarge")
        long_term_memory: Optional conversation summary to include
        starred_messages: Optional list of important messages to include
    
    Returns:
        The constructed system prompt
    """
    
    def get_cutoff_date(model_name: str) -> str:
        """
        Determine the training cutoff date based on the model name.
        
        Args:
            model_name: The name of the model
            
        Returns:
            The cutoff date (e.g., "October 2023", "August 2024")
        """
        model_name_lower = model_name.lower()
        
        # Ministral models - October 2023
        if "ministral" in model_name_lower:
            return "October 2023"
        
        # Gemma 12B - August 2024
        if "gemma" in model_name_lower and ("12b" in model_name_lower or "12" in model_name_lower):
            return "August 2024"
        
        if "nemo" in model_name_lower:
            return "April 2024"
        
        # Default for other large models
        return "August 2024"
    
    if size_category == "tiny":
        # Minimal system prompt for tiny models (<2B)
        sys_prompt = (
            "Tu es un assistant concis et utile. Répond toujours dans la même langue "
            "que la question de l'utilisateur. Ne donne que le contenu pertinent - "
            "sans commentaires ni répétition des consignes."
        )
    elif size_category == "small":
        # Concise system prompt for small models (2-3B)
        sys_prompt = (
            f"You are {model_name}, a concise general assistant. Answer directly in ≤ 8 short lines. "
            "If unsure, say \"Not sure\" and ask 1 brief question. Don't restate the prompt or these rules. "
            "Use only the context sections below if relevant."
        )
    elif size_category == "medium":
        sys_prompt = f"""You are {model_name}, a precise, reliable assistant.

General Guidelines:
- Always respond in the user's language. Do not switch languages mid-response.
- For non-programming tasks (e.g., resumes, summaries, emails), respond in plain, clean natural language.
  Do NOT wrap responses in code blocks or variables unless explicitly requested.
- If JSON or other formats are requested, return clean, copy-ready output without extra explanation unless asked.

Programming Requests:
(Apply only when the user explicitly asks for code, examples, testing, or debugging.)

- Always detect and use the user's language consistently.
- Prefer minimal, correct, tested code examples. When providing code:
  * Use triple backticks with language tags (e.g., ```python).
  * Include necessary imports.
  * Provide a usage snippet or test when appropriate.
- If the user asks to use a specific library or tool, always verify its existence.
  * If it is unknown or cannot be verified, say so clearly and suggest a reliable alternative.
  * Never fabricate code or documentation for libraries, tools, or packages that do not exist.
  * Explain the root cause.
  * Provide a clear, actionable fix.
  * Add a one-line summary of the change.
- Prefer safe, conservative recommendations. For security- or privacy-sensitive instructions, either refuse or suggest a safe approach.
- If the prompt is ambiguous, ask 1–2 clarifying questions before writing code.
- Keep explanations concise and structured. Use numbered steps when listing actions.
- When using external packages, include a pip install line if the package is non-standard.
- For performance/memory optimization questions, include complexity/memory notes and brief trade-off analysis.

End code answers with an optional one-line test or example the user can run locally.

Never include internal hints, model metadata, or training data references. Output only what the user should see."""
    elif size_category == "large":
        # Detailed system prompt for large models (8-15B)
        current_date = datetime.now().strftime("%B %d, %Y")
        cutoff_date = get_cutoff_date(model_name)
        sys_prompt = (
            f"You are {model_name}, a helpful assistant. The current date is {current_date}. "
            f"{model_name}'s training was last updated in {cutoff_date} and it answers user questions "
            f"about events before {cutoff_date} and after {cutoff_date} the same way a highly informed "
            f"individual from {cutoff_date} would if they were talking to someone from {current_date}. "
            "It avoids being repetitive or verbose unless specifically asked. Nobody likes listening to long rants! "
            "IT IS CONCISE. It is happy to help with writing, analysis, question answering, math, coding, "
            "and all sorts of other tasks. It uses markdown for coding."
        )
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
    
    # Add starred messages if there are any
    if starred_messages and len(starred_messages) > 0:
        starred_summary = "\n".join(f"- {msg}" for msg in starred_messages)
        sys_prompt += f"\nImportant points from the conversation so far:\n{starred_summary}"

    # Add long-term memory if provided
    if long_term_memory and long_term_memory.strip():
        sys_prompt += f"\nSummary of the conversation you had so far: {long_term_memory}"
    
    return sys_prompt


def get_prompting_strategy(param_size: int) -> dict:
    """
    Determine optimal prompting strategy based on model size.
    
    Args:
        param_size: Model parameter size in billions.
    
    Returns:
        Dictionary containing strategy configuration flags.
    """
    if param_size <= 2: 
        # Ultra-lightweight strategy for tiny models (<2B)
        return {
            "system_prompt_size_category": "tiny",
            "use_custom_prompt": True,
            "max_history_turns": 2,
            "use_short_term_memory": True,
            "use_middle_term_memory": True,
            "mtm_top_k": 1,
            "use_long_term_memory": False,
            "use_kb_context": True,
            "kb_top_k": 1,
        }
    elif param_size <= 4:  
        # Lightweight strategy for small models (2-4B)
        return {
            "system_prompt_size_category": "small",
            "use_custom_prompt": True,
            "max_history_turns": 3,
            "use_short_term_memory": True,
            "use_middle_term_memory": False,
            "mtm_top_k": 1,
            "use_long_term_memory": False,
            "use_kb_context": True,
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
            "mtm_top_k": 1,
            "use_long_term_memory": True,
            "use_kb_context": True,
            "kb_top_k": 1,
        }
    elif param_size <= 16: 
        # Full strategy for 8-16B models
        return {
            "system_prompt_size_category": "large",
            "use_custom_prompt": True,
            "max_history_turns": 3,
            "use_short_term_memory": True,
            "use_middle_term_memory": True,
            "mtm_top_k": 1,
            "use_long_term_memory": True,
            "use_kb_context": True,
            "kb_top_k": 1,
        }
    else:
        # Maximum strategy for large models (16B+)
        return {
            "system_prompt_size_category": "xlarge",
            "use_custom_prompt": True,
            "max_history_turns": 5,
            "use_short_term_memory": True,
            "use_middle_term_memory": True,
            "mtm_top_k": 2,
            "use_long_term_memory": True,
            "use_kb_context": True,
            "kb_top_k": 3,
        }
