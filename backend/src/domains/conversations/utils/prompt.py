"""
Prompt engineering utilities for conversations.
"""
from typing import List, Optional, Dict
from src.core.logging import logger


class PromptBuilder:
    """
    Handles construction and optimization of prompts for conversation context.
    """
    @staticmethod
    def build_system_prompt(
        model_name: str,
        size_category: str = "medium",
        long_term_memory: Optional[str] = None,
        starred_messages: Optional[List[str]] = None
    ) -> str:
        """
        Build a system prompt based on model size and available context.
        
        Args:
            model_name: Name of the model being used
            size_category: Size category of the model (small/medium/large)
            long_term_memory: Optional conversation summary
            starred_messages: Optional list of important messages
            
        Returns:
            Formatted system prompt
        """
        # Base personality and behavior
        if size_category == "small":
            base_prompt = (
                f"You are {model_name}, a helpful and concise AI assistant. "
                "Provide clear, straightforward answers."
            )
        elif size_category == "medium":
            base_prompt = (
                f"You are {model_name}, a knowledgeable and helpful AI assistant. "
                "Provide clear, well-explained answers while being engaging and natural."
            )
        else:  # large
            base_prompt = (
                f"You are {model_name}, a highly capable AI assistant with broad knowledge. "
                "Provide comprehensive, nuanced answers while being engaging and natural. "
                "Consider multiple perspectives and explain your reasoning when appropriate."
            )

        context_elements = [base_prompt]

        # Add long-term memory if available
        if long_term_memory:
            context_elements.append(
                "\nContext from earlier in the conversation:\n" + long_term_memory
            )

        # Add starred messages if available
        if starred_messages and len(starred_messages) > 0:
            starred_context = "\nImportant points from this conversation:"
            for msg in starred_messages:
                starred_context += f"\n- {msg}"
            context_elements.append(starred_context)

        return "\n".join(context_elements)

    @staticmethod
    def build_query_prompt(
        query: str,
        custom_instructions: Optional[str] = None,
        kb_context: Optional[List[str]] = None,
        relevant_history: Optional[List[str]] = None
    ) -> str:
        """
        Build a query prompt incorporating all available context.
        
        Args:
            query: The user's question
            custom_instructions: Optional specific instructions
            kb_context: Optional relevant knowledge base content
            relevant_history: Optional relevant conversation history
            
        Returns:
            Formatted query prompt
        """
        prompt_elements = []

        # Add relevant conversation history
        if relevant_history:
            prompt_elements.append(
                "These previous messages are relevant to your query:\n" +
                "\n".join(relevant_history)
            )

        # Add knowledge base context
        if kb_context:
            prompt_elements.append(
                "Relevant information from the knowledge base:\n" +
                "\n".join(kb_context)
            )

        # Add custom instructions
        if custom_instructions:
            prompt_elements.append(
                "Additional instructions:\n" + custom_instructions
            )

        # Add the actual query
        prompt_elements.append(query)

        return "\n\n".join(prompt_elements)

    @staticmethod
    def build_title_generation_prompt(
        query: str,
        model_type: str = "mistral"
    ) -> List[Dict[str, str]]:
        """
        Build a prompt for generating a conversation title.
        
        Args:
            query: The text to base the title on
            model_type: The type of model being used
            
        Returns:
            List of message dictionaries for the model
        """
        if model_type == "mistral":
            # For Mistral, combine instructions and query in user message
            prompt = (
                "You are a TITLE generator. Produce ONLY a very short title "
                "(2–4 words maximum).\n"
                "Rules: only the title text; Title Case; no question mark; "
                "no quotes; no emojis; no hashtags; no code; no trailing "
                "punctuation; never answer the question; if empty/URL/noise => "
                "output nothing.\n"
                f"User message: {query}\n"
                "Do not answer the question, only create a relevant title. "
                "Do NOT add quotes around the title.\n"
                "Examples (user question -> title):\n"
                "give me pizza recipe -> Pizza Recipe\n"
                "google founding team members -> Google Founding Team\n"
                "what's the capital of japan -> Japan Capital\n"
                "female of the pig ->  Pig Female Name\n"
            )
            return [{"role": "user", "content": prompt}]
        else:
            # For other models, separate system and user messages
            system_prompt = (
                "You are a very-short-title generator. Return ONLY a concise "
                "title. No punctuation (except apostrophes in possessives), "
                "no quotes, no hashtags, no emojis, no trailing filler words. "
                "Capitalize important words. The title shouldn't be a question.\n"
                "Do not answer the question, only create a relevant title.\n"
                "If the message is empty or meaningless, return nothing.\n"
                "Examples (user question -> title):\n"
                "give me pizza recipe -> Pizza Recipe\n"
                "google founding team members -> Google Founding Team\n"
                "what's the capital of japan -> Japan Capital\n"
                "female of the pig -> Pig Female Name\n"
                "Format: just the title, nothing else."
            )
            user_prompt = f"Create a 2-to-4-word title for:\n{query}"
            return [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]