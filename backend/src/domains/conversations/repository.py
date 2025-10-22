"""
Repository layer for conversation domain.
Handles all database operations.
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status

from src.entities.Conversation import Conversation
from src.entities.Message import Message
from src.entities.Llm import Llm
from src.core.logging import logger


class ConversationRepository:
    """Repository for managing conversation database operations."""
    
    def __init__(self, db: Session):
        """Initialize the repository with a database session."""
        logger.debug("Initializing ConversationRepository")
        self.db = db

    def get_all_conversations(self) -> List[Conversation]:
        """
        Retrieve all conversations.
        
        Returns:
            List of all Conversation objects
            
        Raises:
            HTTPException: If database query fails
        """
        try:
            logger.debug("Retrieving all conversations")
            conversations = self.db.query(Conversation).all()
            logger.debug(f"Retrieved {len(conversations)} conversations")
            return conversations
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving all conversations: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not retrieve conversations"
            )

    def get_conversation_by_id(self, conversation_id: int) -> Optional[Conversation]:
        """
        Retrieve a specific conversation by ID.
        
        Args:
            conversation_id: ID of the conversation to retrieve
            
        Returns:
            The Conversation object if found
            
        Raises:
            HTTPException: If conversation not found or query fails
        """
        try:
            logger.debug(f"Retrieving conversation {conversation_id}")
            conversation = self.db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            
            if not conversation:
                logger.warning(f"Conversation {conversation_id} not found")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Conversation {conversation_id} not found"
                )
                
            logger.debug(
                f"Retrieved conversation {conversation_id} "
                f"with {len(conversation.messages)} messages"
            )
            return conversation
            
        except SQLAlchemyError as e:
            logger.error(
                f"Database error retrieving conversation {conversation_id}: {str(e)}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not retrieve conversation"
            )

    def create_conversation(
        self,
        title: str,
        llm_id: int,
        user_id: Optional[int] = None
    ) -> Conversation:
        """
        Create a new conversation.
        
        Args:
            title: Title for the conversation
            llm_id: ID of the LLM to use
            user_id: Optional ID of the user creating the conversation
            
        Returns:
            The created Conversation
            
        Raises:
            HTTPException: If creation fails
        """
        try:
            conversation = Conversation(
                title=title,
                llm_id=llm_id,
                user_id=user_id
            )
            self.db.add(conversation)
            self.db.commit()
            self.db.refresh(conversation)
            return conversation
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error creating conversation: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not create conversation"
            )

    def get_conversation_messages(
        self,
        conversation_id: int,
        include_metadata: bool = False
    ) -> List[Message]:
        """
        Get all messages in a conversation.
        
        Args:
            conversation_id: ID of the conversation
            include_metadata: Whether to include message metadata
            
        Returns:
            List of Message objects
            
        Raises:
            HTTPException: If conversation not found or query fails
        """
        try:
            logger.debug(
                f"Retrieving messages for conversation {conversation_id}"
            )
            
            # This will raise 404 if conversation not found
            conversation = self.get_conversation_by_id(conversation_id)
            
            query = self.db.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(Message.created_at)
            
            messages = query.all()
            logger.debug(
                f"Retrieved {len(messages)} messages for conversation {conversation_id}"
            )
            
            return messages
            
        except SQLAlchemyError as e:
            logger.error(
                f"Database error retrieving messages for conversation "
                f"{conversation_id}: {str(e)}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not retrieve conversation messages"
            )

    def create_message(
        self,
        conversation_id: int,
        sender: str,
        content: str
    ) -> Message:
        """
        Create a new message in a conversation.
        
        Args:
            conversation_id: ID of the conversation
            sender: Who sent the message ("user" or "assistant") 
            content: The message content
            
        Returns:
            The created Message
            
        Raises:
            HTTPException: If creation fails or conversation not found
        """
        try:
            # Verify conversation exists
            conversation = self.get_conversation_by_id(conversation_id)
            
            message = Message(
                conversation_id=conversation_id,
                sender=sender,
                content=content
            )
            self.db.add(message)
            
            # Update conversation timestamp
            conversation.updated_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(message)
            return message
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error creating message: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not create message"
            )

    def update_conversation(
        self, conversation_id: int, title: str = None, llm_id: int = None
    ) -> Conversation:
        """Update an existing conversation."""
        conversation = self.get_conversation_by_id(conversation_id)
        try:
            if title is not None:
                conversation.title = title
            if llm_id is not None:
                conversation.llm_id = llm_id
            self.db.commit()
            self.db.refresh(conversation)
            return conversation
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error updating conversation {conversation_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not update conversation"
            )

    def delete_conversation(self, conversation_id: int) -> bool:
        """Delete a conversation and its messages."""
        conversation = self.get_conversation_by_id(conversation_id)
        try:
            self.db.delete(conversation)
            self.db.commit()
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error deleting conversation {conversation_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not delete conversation"
            )

    def delete_conversations_bulk(self, conversation_ids: List[int]) -> bool:
        """Delete multiple conversations in bulk."""
        try:
            self.db.query(Conversation).filter(
                Conversation.id.in_(conversation_ids)
            ).delete(synchronize_session=False)
            self.db.commit()
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error bulk deleting conversations: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not delete conversations"
            )


class MessageRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_messages_by_conversation(
        self, conversation_id: int
    ) -> List[Message]:
        """Retrieve all messages for a specific conversation."""
        return (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .all()
        )

    def get_conversation_history(
        self, conversation_id: int
    ) -> List[tuple]:
        """Get conversation history as a list of (sender, message) tuples."""
        try:
            messages = (
                self.db.query(Message.sender, Message.content)
                .filter(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.asc())
                .all()
            )
            return messages
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving conversation history: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not retrieve conversation history"
            )

    def create_message(
        self,
        conversation_id: int,
        content: str,
        sender: str,
        is_error: bool = False
    ) -> Message:
        """Create a new message."""
        try:
            message = Message(
                conversation_id=conversation_id,
                content=content,
                sender=sender,
                is_error=is_error
            )
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)
            return message
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error creating message: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not create message"
            )

    def delete_message(self, message_id: int) -> bool:
        """Delete a specific message."""
        try:
            message = self.db.query(Message).filter(
                Message.id == message_id
            ).first()
            if not message:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Message {message_id} not found"
                )
            self.db.delete(message)
            self.db.commit()
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error deleting message {message_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not delete message"
            )

    def update_message(self, message_id: int, **kwargs) -> Message:
        """Update message properties."""
        try:
            message = self.db.query(Message).filter(
                Message.id == message_id
            ).first()
            if not message:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Message {message_id} not found"
                )
            
            for key, value in kwargs.items():
                if hasattr(message, key):
                    setattr(message, key, value)
            
            self.db.commit()
            self.db.refresh(message)
            return message
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error updating message {message_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not update message"
            )