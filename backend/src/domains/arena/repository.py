"""
Repository layer for arena domain.
Handles all database operations.
"""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status

from src.entities.Llm import Llm
from src.core.logging import logger


class ArenaRepository:
    """Repository for managing arena database operations."""
    
    def __init__(self, db: Session):
        """Initialize the repository with a database session."""
        logger.debug("Initializing ArenaRepository")
        self.db = db

    def get_llm_by_id(self, llm_id: int) -> Llm:
        """
        Retrieve an LLM by ID.
        
        Args:
            llm_id: ID of the LLM to retrieve
            
        Returns:
            The Llm object if found
            
        Raises:
            HTTPException: If LLM not found or query fails
        """
        try:
            logger.debug(f"Retrieving LLM {llm_id}")
            llm = self.db.query(Llm).filter(Llm.id == llm_id).first()
            
            if not llm:
                logger.warning(f"LLM {llm_id} not found")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"LLM {llm_id} not found"
                )
            
            logger.debug(f"Retrieved LLM {llm_id}: {llm.name}")
            return llm
            
        except HTTPException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving LLM {llm_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not retrieve LLM"
            )
