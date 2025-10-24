"""
Pydantic schemas for arena domain.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class ArenaQueryPayload(BaseModel):
    """Schema for arena query requests."""
    
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
        """Ensure question is not just whitespace."""
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
