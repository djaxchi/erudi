"""System-prompt construction + KB-retrieval sizing by model size.

Two helpers consumed by the conversation/arena agent layer:
    build_system_prompt: size-adaptive system prompt (tiny->xlarge tiers) with
        optional starred-message injection.
    get_prompting_strategy: maps a model's parameter count to a system-prompt
        tier + KB-retrieval settings.

The old multi-tier memory (short-term window, middle-term vector search,
long-term summary) is gone: conversation history and the rolling summary now
live in the LangGraph checkpointer (SummarizationMiddleware), so the only
retrieval left here is the Knowledge Base top-k.
"""
from datetime import datetime
from typing import List, Optional



def build_system_prompt(
    model_name: str,
    size_category: str,
    starred_messages: Optional[List[str]] = None,
) -> str:
    """Build a size-adaptive system prompt for ``model_name``.

    Verbosity scales with the model tier (tiny=minimal -> xlarge=comprehensive),
    optionally appending user-starred messages as an "Important points" section.

    Args:
        model_name: Display name of the model (used for self-reference and
            training-cutoff detection on the large tier).
        size_category: One of "tiny", "small", "medium", "large", "xlarge"
            (from ``get_prompting_strategy`` or chosen manually).
        starred_messages: Optional user-starred message contents, appended as a
            bullet list under "Important points from the conversation so far".

    Returns:
        The complete system prompt string.
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
        
        # Gemma 4 - April 2025
        if "gemma" in model_name_lower and ("gemma-4" in model_name_lower or "gemma4" in model_name_lower):
            return "April 2025"

        # Gemma 12B - August 2024
        if "gemma" in model_name_lower and ("12b" in model_name_lower or "12" in model_name_lower):
            return "August 2024"
        
        if "nemo" in model_name_lower:
            return "April 2024"
        
        # Default for other large models
        return "August 2024"
    
    if size_category == "tiny":
        # Descriptive persona only — validated by the #129 eval campaign:
        # on sub-1B models, mechanical rules leak verbatim into answers or
        # prime the very behavior they name ("give 3 to 6 items" produced
        # 52-item lists), while describing tone reliably shapes output.
        sys_prompt = (
            "You are Erudi, a helpful AI assistant. "
            "You answer in the user's language, clearly and directly, in "
            "well-written prose, and you stop when the point is made. "
            "You are warm but efficient, like a knowledgeable friend."
        )
    elif size_category == "small":
        # Descriptive persona — validated by the #129 eval campaign (S0/S1):
        # the old "≤ 8 short lines" cap produced telegraphic answers and the
        # literal "Not sure" phrase was parroting fuel; a 3B under this prompt
        # produced rich, structured answers that stop cleanly. KB grounding
        # does not live here (it rides the per-turn context block).
        sys_prompt = (
            "You are Erudi, a helpful AI assistant. "
            "You answer in the user's language, clearly and accurately, in "
            "well-written prose. You develop your answers with enough depth "
            "to be genuinely useful - structure with short paragraphs, and "
            "use lists only when they make things clearer. You are warm but "
            "efficient, like a knowledgeable friend, and you stop when the "
            "point is made."
        )
    elif size_category == "medium":
        # Descriptive persona — validated by the #129 eval campaign (M0/M1):
        # the ~600-token programming rule sheet cost every turn context weight
        # without measurably helping (the single conditional code sentence
        # below produced equal-or-better code answers: more fenced examples,
        # explicit O(1)/O(n) trade-offs), and everyday answers stay at the
        # M0 level. One voice across tiers; ~600 tokens saved per turn.
        sys_prompt = (
            "You are Erudi, a helpful AI assistant. "
            "You answer in the user's language, clearly and accurately, in "
            "well-written prose. You develop your answers with enough depth "
            "to be genuinely useful - structure with short paragraphs, and "
            "use lists only when they make things clearer. "
            "When the user asks for code, you write minimal, correct, runnable "
            "examples in fenced code blocks with the language tag, include the "
            "imports they need, and mention anything they must install. "
            "You are warm but efficient, like a knowledgeable friend, and you "
            "stop when the point is made."
        )
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

    return sys_prompt


def get_prompting_strategy(param_size: float) -> dict:
    """Select the system-prompt tier + KB context budget for a model size.

    The KB budget is a token ceiling (e5 tokens, ~180/chunk), not a chunk
    count: the adaptive cut in ``kb_utils`` decides per-query how much of it
    to consume. Ceilings follow the measured literature (peak quality scales
    with model size; below ~3B oversized context degrades net accuracy), far
    under even pessimistic effective context windows.

    Args:
        param_size: Model parameter count in billions (e.g. 7 for a 7B model;
            floats like 1.5 are accepted).

    Returns:
        dict with the three keys read downstream:
        - ``system_prompt_size_category``: "tiny"|"small"|"medium"|"large"|"xlarge"
          (consumed by ``build_agent_system_prompt``);
        - ``use_kb_context``: whether to inject Knowledge Base chunks;
        - ``kb_token_budget``: max KB context size in e5 tokens.
    """
    # An unmeasured size (#201) is treated as a small model: the conservative
    # choice keeps the system prompt and KB budget modest rather than assuming a
    # large context a tiny model could not honor.
    if param_size is None or param_size <= 2:
        return {"system_prompt_size_category": "tiny", "use_kb_context": True, "kb_token_budget": 400}
    elif param_size <= 4:
        return {"system_prompt_size_category": "small", "use_kb_context": True, "kb_token_budget": 700}
    elif param_size < 8:
        return {"system_prompt_size_category": "medium", "use_kb_context": True, "kb_token_budget": 1000}
    elif param_size <= 16:
        return {"system_prompt_size_category": "large", "use_kb_context": True, "kb_token_budget": 1400}
    else:
        return {"system_prompt_size_category": "xlarge", "use_kb_context": True, "kb_token_budget": 2000}
