"""Prompt Building and Strategy Utilities for Multi-Tier Memory RAG.

This module provides dynamic system prompt generation and prompting strategy
selection based on model size categories. Implements tiered memory injection
(short-term, middle-term vector, long-term summaries, KB context) optimized
for models ranging from tiny (<2B) to xlarge (16B+).

Key Features:
    - Size-adaptive system prompts (tiny/small/medium/large/xlarge)
    - Multilingual and coding instruction templates
    - Training cutoff date detection (model-specific)
    - Starred message and long-term memory injection
    - Prompting strategy configuration (history turns, top-k, memory flags)

Functions:
    build_system_prompt: Generate system prompt based on model size/context.
    get_prompting_strategy: Get memory and context config for model size.

Size Categories:
    - tiny (<2B): Minimal prompt, 2 history turns, no long-term memory
    - small (2-4B): Concise prompt, 3 turns, short+KB only
    - medium (4-8B): Detailed prompt, 3 turns, all memory layers
    - large (8-16B): Comprehensive prompt, 3 turns, full memory + cutoff dates
    - xlarge (16B+): Sophisticated prompt, 5 turns, max top-k (KB=3, MTM=2)

Prompting Strategy:
    Each size category has optimized settings for:
    - max_history_turns: Number of recent conversation turns to include
    - mtm_top_k: Number of relevant past messages to retrieve (vector search)
    - kb_top_k: Number of knowledge base chunks to inject
    - use_*_memory: Flags for short/middle/long-term memory layers

Examples:
    >>> # Generate system prompt for medium model
    >>> from src.utils.prompt_utils import build_system_prompt
    >>> 
    >>> sys_prompt = build_system_prompt(
    ...     model_name="Mistral 7B Instruct",
    ...     size_category="medium",
    ...     long_term_memory="User is debugging Python FastAPI app",
    ...     starred_messages=["Use async/await for database calls"]
    ... )
    >>> print(sys_prompt[:100])  # First 100 chars
    >>> 
    >>> # Get prompting strategy for model size
    >>> from src.utils.prompt_utils import get_prompting_strategy
    >>> 
    >>> strategy = get_prompting_strategy(param_size=7)  # 7B model
    >>> print(strategy["system_prompt_size_category"])  # "medium"
    >>> print(strategy["max_history_turns"])  # 3
    >>> print(strategy["kb_top_k"])  # 1

Dependencies:
    - src.core.logging: Structured logging

Notes:
    - System prompts emphasize conciseness and user language matching
    - Coding prompts include library verification and error diagnosis guidance
    - Cutoff dates: Ministral (Oct 2023), Gemma 12B (Aug 2024), Nemo (Apr 2024)
    - Starred messages: User-marked important messages injected in system prompt
    - Long-term memory: Conversation summary generated periodically
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
    """Build dynamic system prompt based on model size and conversation context.

    Generates size-appropriate system prompts with injected memory layers
    (long-term summaries, starred messages). Adapts instructions for tiny
    models (minimal) to xlarge models (comprehensive) to maximize performance
    within context window limits.

    Prompt Tiers:
    - **tiny** (<2B): Ultra-concise French instructions, no memory
    - **small** (2-4B): Brief English instructions, context sections hint
    - **medium** (4-8B): Detailed programming + non-programming guidelines
    - **large** (8-16B): Adds training cutoff date awareness, date context
    - **xlarge** (16B+): Sophisticated multi-role instructions, full guidelines

    Args:
        model_name: Display name of the model (e.g., "Mistral 7B Instruct").
            Used in prompt for self-reference and cutoff date detection.
        size_category: Size tier from get_prompting_strategy or manual choice.
            Valid values: "tiny", "small", "medium", "large", "xlarge".
        long_term_memory: Optional conversation summary from previous turns.
            Appended to system prompt as "Summary of the conversation you had so far".
        starred_messages: Optional list of user-starred message contents.
            Appended as bullet list under "Important points from the conversation".

    Returns:
        Complete system prompt string with instructions + injected context.
        Length varies from ~100 chars (tiny) to ~2000 chars (xlarge + context).

    Examples:
        >>> from src.utils.prompt_utils import build_system_prompt
        >>> 
        >>> # Tiny model (minimal)
        >>> prompt = build_system_prompt("Gemma 1B", "tiny")
        >>> print(len(prompt))  # ~120 chars
        >>> 
        >>> # Medium model with memory
        >>> prompt = build_system_prompt(
        ...     model_name="Qwen 2.5 7B",
        ...     size_category="medium",
        ...     long_term_memory="User debugging FastAPI routes",
        ...     starred_messages=["Use async def for endpoints"]
        ... )
        >>> print("Important points" in prompt)  # True
        >>> print("Summary of the conversation" in prompt)  # True
        >>> 
        >>> # Large model with cutoff date
        >>> prompt = build_system_prompt("Mistral Nemo", "large")
        >>> print("April 2024" in prompt)  # True (Nemo cutoff)

    Notes:
        - Cutoff dates: Detected by get_cutoff_date helper (nested function)
        - Language detection: tiny=French, others=English with multilingual support
        - Markdown formatting: Encouraged for code in medium+ tiers
        - Starred messages: Injected as bullet list before long-term memory
        - Long-term memory: Appended last to provide recent conversation context
        - No internal hints: Prompts avoid mentioning system implementation

    See Also:
        get_prompting_strategy: Returns size_category for given param_size
        get_cutoff_date: Nested helper for training cutoff date detection
    """
    
    def get_cutoff_date(model_name: str) -> str:
        """Determine training cutoff date based on model name patterns.

        Detects specific model families and returns their known training
        cutoff dates for use in system prompts.

        Args:
            model_name: Model name (case-insensitive). Checked for patterns
                like "ministral", "gemma", "nemo".

        Returns:
            Cutoff date string (e.g., "October 2023", "August 2024").
            Defaults to "August 2024" if no pattern matched.

        Examples:
            >>> get_cutoff_date("Ministral 8B")  # "October 2023"
            >>> get_cutoff_date("Gemma 2 12B")   # "August 2024"
            >>> get_cutoff_date("Mistral Nemo")  # "April 2024"
            >>> get_cutoff_date("Unknown Model") # "August 2024" (default)

        Notes:
            - Ministral: October 2023
            - Gemma 12B: August 2024
            - Nemo: April 2024
            - Default: August 2024 (conservative estimate for 2024 models)
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
    """Determine optimal prompting strategy based on model parameter size.

    Returns configuration dictionary controlling memory layers, history depth,
    and retrieval top-k values optimized for the given model size. Larger
    models get more context (more turns, higher top-k) while tiny models
    stay minimal to avoid overwhelming limited context windows.

    Strategy Tiers:
    - **≤2B (tiny)**: 2 turns, MTM top-k=1, KB top-k=1, no long-term memory
    - **2-4B (small)**: 3 turns, no MTM, KB top-k=1, no long-term memory
    - **4-8B (medium)**: 3 turns, MTM top-k=1, KB top-k=1, all memory layers
    - **8-16B (large)**: 3 turns, MTM top-k=1, KB top-k=1, all memory layers
    - **>16B (xlarge)**: 5 turns, MTM top-k=2, KB top-k=3, all memory layers

    Args:
        param_size: Model parameter count in billions (e.g., 7 for 7B model).
            Can be float (e.g., 1.5 for 1.5B).

    Returns:
        Dictionary with strategy configuration:
        - system_prompt_size_category: "tiny"|"small"|"medium"|"large"|"xlarge"
        - use_custom_prompt: Always True (enable build_system_prompt)
        - max_history_turns: Number of recent conversation turns to include
        - use_short_term_memory: Always True (recent messages in window)
        - use_middle_term_memory: Vector search for relevant past messages
        - mtm_top_k: Number of middle-term memory chunks to retrieve
        - use_long_term_memory: Conversation summary injection
        - use_kb_context: Knowledge base RAG injection
        - kb_top_k: Number of KB chunks to retrieve

    Examples:
        >>> from src.utils.prompt_utils import get_prompting_strategy
        >>> 
        >>> # Tiny model (1B)
        >>> strategy = get_prompting_strategy(1)
        >>> print(strategy["system_prompt_size_category"])  # "tiny"
        >>> print(strategy["max_history_turns"])  # 2
        >>> print(strategy["use_long_term_memory"])  # False
        >>> 
        >>> # Medium model (7B)
        >>> strategy = get_prompting_strategy(7)
        >>> print(strategy["system_prompt_size_category"])  # "medium"
        >>> print(strategy["max_history_turns"])  # 3
        >>> print(strategy["kb_top_k"])  # 1
        >>> 
        >>> # XLarge model (70B)
        >>> strategy = get_prompting_strategy(70)
        >>> print(strategy["system_prompt_size_category"])  # "xlarge"
        >>> print(strategy["max_history_turns"])  # 5
        >>> print(strategy["kb_top_k"])  # 3

    Notes:
        - All strategies enable short-term memory (recent turns in window)
        - Small models skip middle-term memory to save context space
        - Tiny/small models skip long-term summaries to stay minimal
        - XLarge models get 5 turns (vs 3 for others) and higher top-k
        - KB retrieval scales: tiny/small/medium/large=1, xlarge=3
        - MTM retrieval: tiny/medium/large=1, xlarge=2, small=disabled

    See Also:
        build_system_prompt: Uses system_prompt_size_category from this
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
