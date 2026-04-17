"""Pydantic validation schemas for fine-tuning job creation (STUB).

Defines request schemas for the training domain. Currently used only by commented-out
training endpoint. Will be activated when multi-engine training adapters are implemented.

Example:
    from src.domains.training.schemas import TrainingInfo

    payload = TrainingInfo(
        paths=["/uploads/training_data.pdf"],
        selectedModel=42,
        modelName="Custom-Llama-3-8B-Finance"
    )
"""
from pydantic import BaseModel
from typing import List

class TrainingInfo(BaseModel):
    """Request schema for fine-tuning job creation (STUB - not currently used).

    Attributes:
        paths: List of PDF file paths containing training data.
        selectedModel: Database ID of base LLM to fine-tune.
        modelName: Name for the fine-tuned model (e.g., "Custom-Llama-3-Finance").

    Example:
        >>> training_req = TrainingInfo(
        ...     paths=["/uploads/finance_docs.pdf", "/uploads/regulations.pdf"],
        ...     selectedModel=42,
        ...     modelName="Llama-3-8B-Financial-Advisor"
        ... )
    """
    paths: List[str]
    selectedModel: int
    modelName: str
