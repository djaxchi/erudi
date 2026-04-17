"""Pydantic validation schemas for arena stateless queries.

Defines request schemas for the arena domain, validating query parameters and
generation settings for stateless LLM testing.

Example:
    from src.domains.arena.schemas import ArenaQueryPayload

    query = ArenaQueryPayload(
        question="What is quantum computing?",
        temperature=0.7,
        top_p=0.9,
        max_new_tokens=512,
        custom_prompt="Use simple language"
    )
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class ArenaQueryPayload(BaseModel):
    """Request schema for stateless arena queries with generation parameters.

    Validates user input for arena LLM queries, enforcing ranges for sampling parameters
    and ensuring non-empty questions. Includes optional custom instructions for specialized
    prompting.

    Attributes:
        question: The question/prompt to send to the model (min 1 char, trimmed).
        temperature: Sampling temperature (0.0=deterministic, 2.0=creative, default=0.1).
        top_p: Nucleus sampling threshold (0.0-1.0, default=0.5).
        max_new_tokens: Maximum tokens to generate (1-8192, default=1024).
        custom_prompt: Optional additional instructions appended to system prompt.

    Example:
        >>> payload = ArenaQueryPayload(
        ...     question="Explain relativity",
        ...     temperature=0.7,
        ...     top_p=0.9,
        ...     max_new_tokens=512,
        ...     custom_prompt="Use analogies"
        ... )
    """
    
    question: str = Field(
        ...,
        min_length=1,
        description="The question to ask the model"
    )
    temperature: Optional[float] = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0.0-2.0)"
    )
    top_p: Optional[float] = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling threshold (0.0-1.0)"
    )
    max_new_tokens: Optional[int] = Field(
        default=1024,
        ge=1,
        le=8192,
        description="Maximum number of tokens to generate"
    )
    custom_prompt: Optional[str] = Field(
        default=None,
        description="Optional additional instructions for the model"
    )

    @field_validator('question')
    @classmethod
    def validate_question(cls, v: str) -> str:
        """Ensure question is not empty or whitespace-only.

        Args:
            v: The question string to validate.

        Returns:
            Trimmed question string.

        Raises:
            ValueError: If question is empty or whitespace-only.
        """
        if not v or not v.strip():
            raise ValueError("Question cannot be empty or whitespace")
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {
                "question": "What is the capital of France?",
                "temperature": 0.7,
                "top_p": 0.9,
                "max_new_tokens": 512,
                "custom_prompt": "Please answer concisely."
            }
        }
