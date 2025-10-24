"""Pydantic validation schemas for Knowledge Base creation and status responses.

Defines data transfer objects for Knowledge Base assistant creation workflow. Schemas
validate document paths, base model selection, and assistant metadata.

Example:
    from src.domains.knowledge_base.schemas import KnowledgeBaseCreate
    import requests

    payload = KnowledgeBaseCreate(
        paths=["/uploads/report1.pdf", "/uploads/report2.txt"],
        selectedModel=42,
        modelName="Financial Assistant",
        description="Q1-Q4 2024 earnings reports"
    )
    response = requests.post("/knowledge_base/create", json=payload.model_dump())
"""
from pydantic import BaseModel
from typing import List

class KnowledgeBaseCreate(BaseModel):
    """Request schema for creating or updating a Knowledge Base assistant.

    Attributes:
        paths: List of absolute file paths to PDF/TXT documents to ingest.
        selectedModel: Database ID of base LLM to specialize with KB attachment.
        modelName: Name for the new specialized assistant (e.g., "Financial Reports Bot").
        description: Optional user annotation describing the KB's purpose or domain.

    Example:
        >>> kb_req = KnowledgeBaseCreate(
        ...     paths=["/uploads/q1.pdf", "/uploads/q2.pdf"],
        ...     selectedModel=42,
        ...     modelName="Earnings Reports Assistant",
        ...     description="2024 Q1-Q4 financial data"
        ... )
    """
    paths: List[str]
    selectedModel: int
    modelName: str
    description: str = None

class KnowledgeBaseResponse(BaseModel):
    """Response schema for KB creation endpoint with async processing confirmation.

    Attributes:
        msg: Human-readable status message (e.g., "Knowledge Base Assistant is being created.").
        model_id: Database ID of the newly created specialized LLM (poll /kb/{model_id}/status).

    Example:
        >>> response = KnowledgeBaseResponse(
        ...     msg="Knowledge Base Assistant is being created.",
        ...     model_id=108
        ... )
        >>> # Client polls GET /knowledge_base/108/status until status="completed"
    """
    msg: str
    model_id: int