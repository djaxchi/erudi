"""
Services for managing conversations and message processing.
"""
from datetime import datetime
from typing import List, Tuple, Optional

from src.core.logging import logger
from src.domains.conversations.repository import ConversationRepository
from src.domains.conversations.utils.cache import ConversationCache
from src.domains.conversations.utils.embedding import ConversationEmbedder
from src.domains.conversations.utils.prompt import PromptGenerator
from src.entities.Conversation import Conversation
from src.entities.Message import Message


class ConversationService:
    """Service for managing conversations and message processing."""
    
    def __init__(
        self,
        repository: ConversationRepository,
        embedder: ConversationEmbedder,
        cache: ConversationCache,
        prompt_generator: PromptGenerator
    ):
        """
        Initialize the conversation service.
        
        Args:
            repository: Repository for conversation storage
            embedder: Utility for message embedding and similarity search
            cache: Cache for conversation summaries and embeddings
            prompt_generator: Utility for generating prompts
        """
        logger.info("Initializing ConversationService")
        self.repository = repository
        self.embedder = embedder
        self.cache = cache
        self.prompt_generator = prompt_generator
        logger.debug(
            "ConversationService initialized with: "
            f"repository={repository.__class__.__name__}, "
            f"embedder={embedder.__class__.__name__}, "
            f"cache={cache.__class__.__name__}, "
            f"prompt_generator={prompt_generator.__class__.__name__}"
        )

    async def get_conversation_context(
        self,
        conversation_id: int,
        query: str,
        max_context_length: int = 2000
    ) -> str:
        """
        Get relevant context for a query within a conversation.
        
        Args:
            conversation_id: ID of the conversation
            query: The current query/message
            max_context_length: Maximum length of context to return
            
        Returns:
            String containing relevant conversation context
        """
        logger.debug(
            f"Getting context for conversation {conversation_id} "
            f"with query: {query[:50]}..."
        )
        
        try:
            # Get conversation history with metadata
            history = await self.repository.get_conversation_messages(
                conversation_id,
                include_metadata=True
            )
            
            if not history:
                logger.info(
                    f"No history found for conversation {conversation_id}"
                )
                return ""
                
            logger.debug(
                f"Found {len(history)} messages in conversation {conversation_id}"
            )
                
            # Convert to format needed by embedder
            formatted_history = [
                (msg.id, msg.sender, msg.content, msg.created_at)
                for msg in history
            ]
            
            # Find semantically relevant messages
            relevant_messages = self.embedder.find_relevant_messages(
                conversation_id=conversation_id,
                query=query,
                history=formatted_history,
                n_results=5,
                cache=self.cache
            )
            
            logger.debug(
                f"Found {len(relevant_messages)} relevant messages "
                f"for conversation {conversation_id}"
            )
            
            # Generate prompt with context
            context = self.prompt_generator.generate_with_context(
                query=query,
                relevant_messages=relevant_messages,
                max_length=max_context_length
            )
            
            logger.debug(
                f"Generated context of length {len(context)} "
                f"for conversation {conversation_id}"
            )
            
            return context
            
        except Exception as e:
            logger.exception(
                f"Error getting conversation context: {str(e)}. "
                f"conversation_id={conversation_id}, query={query[:50]}..."
            )
            return ""
            return ""
            
    async def add_message(
        self,
        conversation_id: int,
        sender: str,
        content: str
    ) -> Optional[Message]:
        """
        Add a new message to a conversation.
        
        Args:
            conversation_id: ID of the conversation
            sender: Who sent the message ("user" or "assistant")
            content: The message content
            
        Returns:
            The created Message object, or None if creation failed
        """
        try:
            # Create message in database
            message = await self.repository.create_message(
                conversation_id=conversation_id,
                sender=sender,
                content=content
            )
            
            if not message:
                return None
                
            # Update cache with new message
            self.cache.add_message_embedding(
                conversation_id=conversation_id,
                message_id=message.id,
                sender=sender,
                content=content,
                embedding=self.embedder.embed_messages([content])[0],
                timestamp=message.created_at
            )
            
            return message
            
        except Exception as e:
            logger.exception(f"Error adding message: {str(e)}")
            return None

    async def create_conversation(
        self,
        user_id: int,
        title: str = ""
    ) -> Optional[Conversation]:
        """
        Create a new conversation.
        
        Args:
            user_id: ID of the user creating the conversation
            title: Optional title for the conversation
            
        Returns:
            The created Conversation object, or None if creation failed
        """
        try:
            conversation = await self.repository.create_conversation(
                user_id=user_id,
                title=title
            )
            
            if conversation:
                # Initialize cache for new conversation
                self.cache.initialize_conversation(conversation.id)
                
            return conversation
            
        except Exception as e:
            logger.exception(f"Error creating conversation: {str(e)}")
            return None
