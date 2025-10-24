"""
Arena endpoints for stateless LLM queries.
"""
from fastapi import Depends, APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.database.core import get_db
from src.domains.arena.schemas import ArenaQueryPayload
from src.domains.arena.services import ArenaService
from src.core.logging import logger

router = APIRouter(prefix="/arena", tags=["arena"])


def get_arena_service(db: Session = Depends(get_db)) -> ArenaService:
    """Provide an arena service instance."""
    return ArenaService(db)


@router.post("/{llm_id}/query")
async def query_arena(
    llm_id: int,
    payload: ArenaQueryPayload,
    service: ArenaService = Depends(get_arena_service)
):
    """
    Stateless arena query for testing LLMs without conversation history.
    
    Args:
        llm_id: ID of the model to query
        payload: Query payload with question and optional parameters
        
    Returns:
        Streaming response with model-generated text
        
    Query Parameters:
        - question: The question to ask the model
        - temperature: Sampling temperature (default: 0.1)
        - top_p: Nucleus sampling threshold (default: 0.5)
        - max_new_tokens: Maximum tokens to generate (default: 1024)
        - custom_prompt: Optional additional instructions
    """
    logger.info(f"Arena query request for LLM {llm_id}")
    
    return StreamingResponse(
        service.query_llm_stream(llm_id, payload),
        media_type="text/plain"
    )