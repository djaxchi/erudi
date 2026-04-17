"""
Repository layer for conversation domain.
Handles all database operations.
"""
from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.entities.Conversation import Conversation
from src.entities.Message import Message
from src.entities.Llm import Llm
from src.core.logging import logger
from src.core.exceptions import (
    ConversationNotFoundException,
    ModelNotFoundException,
    DatabaseException,
    MessageNotFoundException,
)


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
            DatabaseException: If database query fails
        """
        try:
            logger.debug("Retrieving all conversations")
            conversations = self.db.query(Conversation).all()
            logger.debug(f"Retrieved {len(conversations)} conversations")
            return conversations
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving all conversations: {str(e)}")
            raise DatabaseException(
                "Could not retrieve conversations",
                trace=str(e)
            )

    def get_conversation_by_id(self, conversation_id: int) -> Conversation:
        """
        Retrieve a specific conversation by ID.
        
        Args:
            conversation_id: ID of the conversation to retrieve
            
        Returns:
            The Conversation object if found
            
        Raises:
            ConversationNotFoundException: If conversation not found
            DatabaseException: If database query fails
        """
        try:
            logger.debug(f"Retrieving conversation {conversation_id}")
            conversation = self.db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            
            if not conversation:
                logger.warning(f"Conversation {conversation_id} not found")
                raise ConversationNotFoundException(conversation_id)
                
            logger.debug(
                f"Retrieved conversation {conversation_id} "
                f"with {len(conversation.messages)} messages"
            )
            return conversation
            
        except ConversationNotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(
                f"Database error retrieving conversation {conversation_id}: {str(e)}"
            )
            raise DatabaseException(
                "Could not retrieve conversation",
                trace=str(e)
            )

    def get_llm_by_id(self, llm_id: int) -> Llm:
        """
        Retrieve an LLM by ID.
        
        Args:
            llm_id: ID of the LLM to retrieve
            
        Returns:
            The Llm object if found
            
        Raises:
            ModelNotFoundException: If LLM not found
            DatabaseException: If database error occurs
        """
        try:
            llm = self.db.query(Llm).filter(Llm.id == llm_id).first()
            if not llm:
                raise ModelNotFoundException(f"LLM {llm_id}")
            return llm
        except ModelNotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving LLM {llm_id}: {str(e)}")
            raise DatabaseException(
                "Could not retrieve LLM",
                trace=str(e)
            )

    def create_conversation(
        self,
        llm_id: int,
        name: str = "New Conversation",
        temperature: float = 0.2,
        top_p: float = 0.5,
        max_tokens: int = 1024,
        custom_prompt: str = ""
    ) -> Conversation:
        """
        Create a new conversation.
        
        Args:
            llm_id: ID of the LLM to use
            name: Name for the conversation
            temperature: Sampling temperature
            top_p: Nucleus sampling threshold
            max_tokens: Maximum tokens to generate
            custom_prompt: Custom system prompt
            
        Returns:
            The created Conversation
            
        Raises:
            DatabaseException: If creation fails
        """
        try:
            conversation = Conversation(
                llm_id=llm_id,
                name=name,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                custom_prompt=custom_prompt
            )
            self.db.add(conversation)
            self.db.flush()  # Flush to get ID, no commit
            logger.info(f"Created conversation {conversation.id}")
            return conversation
            
        except SQLAlchemyError as e:
            logger.error(f"Error creating conversation: {str(e)}")
            raise DatabaseException(
                "Could not create conversation",
                trace=str(e)
            )

    def update_conversation(
        self,
        conversation_id: int,
        name: Optional[str] = None,
        llm_id: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        custom_prompt: Optional[str] = None
    ) -> Conversation:
        """
        Update an existing conversation.
        
        Args:
            conversation_id: ID of the conversation to update
            name: New name
            llm_id: New LLM ID
            temperature: New temperature
            top_p: New top_p
            max_tokens: New max_tokens
            custom_prompt: New custom prompt
            
        Returns:
            Updated Conversation object
            
        Raises:
            ConversationNotFoundException: If conversation not found
            DatabaseException: If update fails
        """
        try:
            conversation = self.get_conversation_by_id(conversation_id)
            
            updated = False
            
            if name is not None and name != conversation.name:
                conversation.name = name
                updated = True
            
            if llm_id is not None and llm_id != conversation.llm_id:
                conversation.llm_id = llm_id
                updated = True
            
            if temperature is not None and temperature != conversation.temperature:
                conversation.temperature = temperature
                updated = True
            
            if top_p is not None and top_p != conversation.top_p:
                conversation.top_p = top_p
                updated = True
            
            if max_tokens is not None and max_tokens != conversation.max_tokens:
                conversation.max_tokens = max_tokens
                updated = True
            
            if custom_prompt is not None and custom_prompt != conversation.custom_prompt:
                conversation.custom_prompt = custom_prompt
                updated = True
            
            if updated:
                self.db.flush()  # Flush changes, no commit
                logger.info(f"Updated conversation {conversation_id}")
            
            return conversation
            
        except ConversationNotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Error updating conversation {conversation_id}: {str(e)}")
            raise DatabaseException(
                "Could not update conversation",
                trace=str(e)
            )

    def delete_conversation(self, conversation_id: int) -> None:
        """
        Delete a conversation and its messages.
        
        Args:
            conversation_id: ID of the conversation to delete
            
        Raises:
            ConversationNotFoundException: If conversation not found
            DatabaseException: If deletion fails
        """
        try:
            conversation = self.get_conversation_by_id(conversation_id)
            self.db.delete(conversation)
            self.db.flush()  # Flush deletion, no commit
            logger.info(f"Deleted conversation {conversation_id}")
        except ConversationNotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Error deleting conversation {conversation_id}: {str(e)}")
            raise DatabaseException(
                "Could not delete conversation",
                trace=str(e)
            )

    def delete_conversations_bulk(self, conversation_ids: List[int]) -> None:
        """
        Delete multiple conversations in bulk.
        
        Args:
            conversation_ids: List of conversation IDs to delete
            
        Raises:
            DatabaseException: If deletion fails
        """
        try:
            self.db.query(Conversation).filter(
                Conversation.id.in_(conversation_ids)
            ).delete(synchronize_session=False)
            self.db.flush()  # Flush deletions, no commit
            logger.info(f"Bulk deleted {len(conversation_ids)} conversations")
        except SQLAlchemyError as e:
            logger.error(f"Error bulk deleting conversations: {str(e)}")
            raise DatabaseException(
                "Could not delete conversations",
                trace=str(e)
            )

    def update_last_message_time(self, conversation_id: int) -> None:
        """
        Update the last_message_time of a conversation.
        
        Args:
            conversation_id: ID of the conversation
        """
        try:
            conversation = self.get_conversation_by_id(conversation_id)
            conversation.updated_at = datetime.utcnow()
            self.db.flush()  # Flush update, no commit
        except ConversationNotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Error updating last message time: {str(e)}")
            raise DatabaseException(
                "Could not update conversation timestamp",
                trace=str(e)
            )


class MessageRepository:
    """Repository for managing message database operations."""
    
    def __init__(self, db: Session):
        """Initialize the repository with a database session."""
        logger.debug("Initializing MessageRepository")
        self.db = db

    def get_messages_by_conversation(
        self, conversation_id: int
    ) -> List[Message]:
        """
        Retrieve all messages for a specific conversation.
        
        Args:
            conversation_id: ID of the conversation
            
        Returns:
            List of Message objects
        """
        try:
            messages = (
                self.db.query(Message)
                .filter(Message.conversation_id == conversation_id)
                .order_by(Message.timestamp)
                .all()
            )
            logger.debug(f"Retrieved {len(messages)} messages for conversation {conversation_id}")
            return messages
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving messages: {str(e)}")
            raise DatabaseException(
                "Could not retrieve messages",
                trace=str(e)
            )

    def get_conversation_history(
        self, conversation_id: int
    ) -> List[Tuple[int, str, str, any]]:
        """
        Get conversation history as a list of (sender, content) tuples.
        
        Args:
            conversation_id: ID of the conversation
            
        Returns:
            List of (id, sender, content, timestamp) tuples ordered by timestamp
        """
        try:
            messages = (
                self.db.query(Message.id, Message.sender, Message.content, Message.timestamp)
                .filter(Message.conversation_id == conversation_id)
                .order_by(Message.timestamp.asc())
                .all()
            )
            logger.debug(f"Retrieved history with {len(messages)} messages")
            return [(msg.id, msg.sender, msg.content, msg.timestamp) for msg in messages]
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving conversation history: {str(e)}")
            return []

    def get_starred_messages(self, conversation_id: int) -> List[str]:
        """
        Get all starred messages in a conversation.
        
        Args:
            conversation_id: ID of the conversation
            
        Returns:
            List of starred message contents
        """
        try:
            messages = (
                self.db.query(Message.content)
                .filter(
                    Message.conversation_id == conversation_id,
                    Message.starred == True
                )
                .all()
            )
            return [msg.content for msg in messages]
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving starred messages: {str(e)}")
            return []

    def create_message(
        self,
        conversation_id: int,
        content: str,
        sender: str,
    ) -> Message:
        """
        Create a new message.
        
        Args:
            conversation_id: ID of the conversation
            content: Message content
            sender: Message sender ("user" or "llm")
            
        Returns:
            The created Message object
            
        Raises:
            DatabaseException: If creation fails
        """
        try:
            message = Message(
                conversation_id=conversation_id,
                content=content,
                sender=sender
            )
            self.db.add(message)
            self.db.flush()  # Flush to get ID, no commit
            logger.debug(f"Created message {message.id} in conversation {conversation_id}")
            return message
        except SQLAlchemyError as e:
            logger.error(f"Error creating message: {str(e)}")
            raise DatabaseException(
                "Could not create message",
                trace=str(e)
            )

    def delete_message(self, message_id: int) -> None:
        """
        Delete a specific message.
        
        Args:
            message_id: ID of the message to delete
            
        Raises:
            MessageNotFoundException: If message not found
            DatabaseException: If deletion fails
        """
        try:
            message = self.db.query(Message).filter(
                Message.id == message_id
            ).first()
            if not message:
                raise MessageNotFoundException(message_id)
            self.db.delete(message)
            self.db.flush()  # Flush deletion, no commit
            logger.info(f"Deleted message {message_id}")
        except MessageNotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Error deleting message {message_id}: {str(e)}")
            raise DatabaseException(
                "Could not delete message",
                trace=str(e)
            )

    def star_message(self, message_id: int) -> None:
        """
        Star a message by its ID.
        
        Args:
            message_id: ID of the message to star
            
        Raises:
            MessageNotFoundException: If message not found
            DatabaseException: If update fails
        """
        try:
            message = self.db.query(Message).filter(
                Message.id == message_id
            ).first()
            if not message:
                raise MessageNotFoundException(message_id)
            message.starred = True
            self.db.flush()  # Flush update, no commit
            logger.info(f"Starred message {message.id}")
        except MessageNotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Failed to star message {message_id}")
            raise DatabaseException(
                "Failed to star message",
                trace=str(e)
            )

    def unstar_message(self, message_id: int) -> None:
        """
        Unstar a message by its ID.
        
        Args:
            message_id: ID of the message to unstar
            
        Raises:
            MessageNotFoundException: If message not found
            DatabaseException: If update fails
        """
        try:
            message = self.db.query(Message).filter(
                Message.id == message_id
            ).first()
            if not message:
                raise MessageNotFoundException(message_id)
            message.starred = False
            self.db.flush()  # Flush update, no commit
            logger.info(f"Unstarred message {message.id}")
        except MessageNotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Failed to unstar message {message_id}")
            raise DatabaseException(
                "Failed to unstar message",
                trace=str(e)
            )
