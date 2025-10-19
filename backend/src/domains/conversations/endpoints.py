
import numpy as np
from datetime import datetime
from typing import List
import faiss

from fastapi import Depends, HTTPException, Body, status, APIRouter
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse

from src.database.core import get_db

from src.entities.Conversation import Conversation
from src.entities.Llm import Llm
from src.entities.Message import Message
from src.core import vars
from src.core.logging import logger
from src.utils.inference_utils import (
    EmbedderService,
    get_prompting_strategy,
    get_relevant_texts_from_kb,
    build_system_prompt,
)
from src.domains.conversations.schemas import (
    ConversationCreate,
    ConversationDeleteBulk,
    ConversationQuery,
    ConversationResponse,
    ConversationUpdate,
    ConversationWithMessagesResponse,
    MessageResponse
)

router = APIRouter(prefix="/conversations", tags=["conversations"])

_conversation_summary_cache = {}



@router.get(
    "/{conversation_id}/fetch_messages",
    response_model=List[MessageResponse],
)
async def get_messages_by_conversation(
    conversation_id: int, db: Session = Depends(get_db)
):
    """
    Fetch all messages for a specific conversation.
    """
    messages = (
        db.query(Message).filter(Message.conversation_id == conversation_id).all()
    )
    return messages


@router.delete("/messages/{message_id}")
async def delete_message(message_id: int, db: Session = Depends(get_db)):
    """
    Delete a specific message by its ID.
    """
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    db.delete(message)
    db.commit()
    return {"message": "Message deleted successfully"}


@router.get("/", response_model=List[ConversationResponse])
async def get_all_conversations(db: Session = Depends(get_db)):
    """
    Fetch all conversations.
    """
    try:
        conversations = db.query(Conversation).all()
        # Use model_validate for serialization (from_orm deprecated)
        # return [ConversationResponse.model_validate(conv) for conv in conversations]
        return conversations
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@router.get(
    "/{conversation_id}", response_model=ConversationWithMessagesResponse
)
async def get_conversation_by_id(conversation_id: int, db: Session = Depends(get_db)):
    """
    Fetch a single conversation by its ID, including messages.
    """
    conversation = (
        db.query(Conversation).filter(Conversation.id == conversation_id).first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.post("/", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
):
    """Create a new conversation for a specific LLM (body JSON)."""

    conversation = Conversation(
        llm_id=payload.llm_id,
        name="New Conversation",
        temperature=payload.temperature,
        top_p=payload.top_p,
        max_tokens=payload.max_tokens,
        custom_prompt=payload.custom_prompt,
    )
    try:
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not create conversation: {str(e)}",
        )
    return conversation


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """
    Delete a conversation by its ID.
    """
    conversation = (
        db.query(Conversation).filter(Conversation.id == conversation_id).first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    global _conversation_summary_cache
    if conversation_id in _conversation_summary_cache:
        del _conversation_summary_cache[conversation_id]
        logger.info(
            f"Cleared summary cache for deleted conversation {conversation_id}"
        )

    db.delete(conversation)
    db.commit()
    return {"message": "Conversation deleted successfully"}


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: int,
    payload: ConversationUpdate,
    db: Session = Depends(get_db),
):
    """Update conversation fields (name and llm_id)."""

    conversation = (
        db.query(Conversation).filter(Conversation.id == conversation_id).first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    updated = False

    if payload.name is not None and payload.name != conversation.name:
        conversation.name = payload.name
        updated = True

    if payload.llm_id is not None and payload.llm_id != conversation.llm_id:
        conversation.llm_id = payload.llm_id
        updated = True

    if (
        payload.temperature is not None
        and payload.temperature != conversation.temperature
    ):
        conversation.temperature = payload.temperature
        updated = True

    if payload.top_p is not None and payload.top_p != conversation.top_p:
        conversation.top_p = payload.top_p
        updated = True

    if payload.max_tokens is not None and payload.max_tokens != conversation.max_tokens:
        conversation.max_tokens = payload.max_tokens
        updated = True

    if (
        payload.custom_prompt is not None
        and payload.custom_prompt != conversation.custom_prompt
    ):
        conversation.custom_prompt = payload.custom_prompt
        updated = True

    if updated:
        try:
            db.commit()
            db.refresh(conversation)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Could not update conversation: {str(e)}",
            )

    return conversation


def get_conversation_history(db: Session, conversation_id: int) -> List[tuple]:
    try:
        messages = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.timestamp.asc())
            .all()
        )
        messages_to_be_returned = []

        if len(messages) == 0:
            return messages_to_be_returned

        for msg in messages:
            messages_to_be_returned.append((msg.sender, msg.content))

        return messages_to_be_returned
    except Exception as e:
        logger.exception(f"Error retrieving conversation history: {e}")
        return []


def retrieve_context(
    query: str,
    conversation_history: List,
    conversation_id: int,
    llm: Llm,
    db: Session,
    strategy: dict,
    n_last_turns: int = 1,
    model_type: str = "mistral",
) -> dict:
    """
    Retrieve relevant context from the conversation history based on semantic similarity and recency.
    Uses SentenceTransformer for embeddings and FAISS for similarity search.
    Args:
        query (str): The user's query.
        conversation_history (list): List of (sender, message) tuples.
        conversation_id (int): The ID of the conversation for caching purposes.
        llm (Llm): The LLM model object.
        db (Session): Database session.
        strategy (dict): Prompting strategy configuration based on model size.
        n_last_turns (int): Number of last turns to include.
        model_type (str): The type of model to use for prompt engineering.
    Returns:
        dict :
        {   context_str (str) : Formatted context string.
            long_term_memory (str) : long-term-memory (conversation summary by llm)
            middle_term_memory (list) : middle-term-memory (top_k most relevant turns relative to the user query)
            kb_cont (list) : knowledge base context (if LLM is attached to a KB)
        }
    """

    context = {
        "context_str": None,
        "long_term_memory": None,
        "middle_term_memory": None,
        "kb_context": None,
    }

    def get_cached_summary(conversation_id: int, current_message_count: int):
        """Get cached summary or determine if regeneration is needed."""
        global _conversation_summary_cache

        if conversation_id not in _conversation_summary_cache:
            return None, True

        cache_entry = _conversation_summary_cache[conversation_id]
        cached_count = cache_entry["message_count"]

        if current_message_count >= cached_count * 2:
            logger.info(
                f"Summary cache expired for conversation {conversation_id}: {cached_count} -> {current_message_count} messages"
            )
            return None, True

        logger.info(
            f"Using cached summary for conversation {conversation_id}: {cached_count} messages"
        )
        return cache_entry["summary"], False

    def cache_summary(conversation_id: int, summary: str, message_count: int):
        """Cache the generated summary."""
        global _conversation_summary_cache
        _conversation_summary_cache[conversation_id] = {
            "summary": summary,
            "message_count": message_count,
            "generated_at": datetime.now(),
        }
        logger.info(
            f"Cached summary for conversation {conversation_id} with {message_count} messages"
        )

    def generate_conversation_summary(history, model_type="mistral"):
        """
        Generate a quick summary of the conversation history.
        Args:
            history (list): List of (sender, message) tuples.
            model_type (str): The type of model to use for summarization.
        Returns:
            str: The generated summary.
        """
        model, tokenizer = vars.LLM_Engine.get_model_and_tokenizer(llm_id=llm.id, llm_local_path=llm.link)
        if len(history) < 10:
            return ""

        conv_text = ""
        for sender, msg in history:
            role = "User" if sender == "user" else "Assistant"
            conv_text += f"{role}: {msg}\n"

        # THIS IS TO FIX IN ORDER TO KEEP ALL OF TRHE CONTEXT, BY CHUNKS AND NOT BY TRUNCKING AFTER 4000 CHAR
        if len(conv_text) > 4000:
            conv_text = conv_text[:4000] + "..."

        summary_sys_prompt = f"""You are a conversation summarizer. Create a concise summary of the key topics, decisions, and important information discussed in this conversation. Keep it under 100 words. No formatting needed, only a few phrases."""
        summary_user_prompt = f"""Summarize this conversation:

        {conv_text}

        Summary:"""

        try:
            # Merge system prompt into user message for models that don't support system role
            merged_summary_prompt = f"{summary_sys_prompt}\n\n{summary_user_prompt}"

            logger.info("======= Generating conversation summary... =======")
            summary = ""

            for chunk in vars.LLM_Engine.generate_stream(
                model=model,
                tokenizer=tokenizer,
                prompt=merged_summary_prompt,
                max_tokens=150,
                temperature=1,
                top_p=0.2,
                repetition_penalty=1.3,
                repetition_context_size=150,
            ):
                summary += chunk

            return summary

        except Exception as e:
            logger.exception(f"Summary generation failed: {e}")
            return ""

    context_lines = []
    current_message_count = len(conversation_history)

    # Long-term memory (Conversation summary) - only if strategy allows
    summary_threshold = n_last_turns * 2 * 2
    if (
        strategy["use_long_term_memory"]
        and len(conversation_history) > summary_threshold
    ):
        cached_summary, need_regenerate = get_cached_summary(
            conversation_id, current_message_count
        )

        if need_regenerate:
            logger.info(
                f"Generating new conversation summary for {len(conversation_history)} messages"
            )
            long_term_memory = generate_conversation_summary(
                conversation_history, model_type=model_type
            )
            if long_term_memory:
                cache_summary(
                    conversation_id, long_term_memory, current_message_count + 1
                )
        else:
            long_term_memory = cached_summary

        if long_term_memory:
            context_lines.append("  - Conversation Summary:\n")
            context_lines.append(f"{long_term_memory}")
            context_lines.append("")
            context["long_term_memory"] = long_term_memory

    n_recent = n_last_turns * 2
    if len(conversation_history) >= n_recent + 4:
        semantic_history = conversation_history[:-n_recent]
    else:
        semantic_history = []

    # Middle-term memory (Semantic context) - only if strategy allows
    if strategy["use_middle_term_memory"] and len(semantic_history) >= 2:
        n_to_retrieve = (
            strategy["mtm_top_k"]
            if len(semantic_history) >= 2 * strategy["mtm_top_k"]
            else int(len(semantic_history) / 2)
        )
        embedder = EmbedderService.get_embedder()
        query_emb = embedder.encode(query, convert_to_tensor=True)
        messages = [msg[1] for msg in semantic_history]
        msg_embs = embedder.encode(messages, convert_to_tensor=False)
        EmbedderService.cleanup()
        index = faiss.IndexFlatL2(len(msg_embs[0]))
        index.add(np.array(msg_embs))
        _, idxs = index.search(np.array([query_emb.cpu().numpy()]), k=n_to_retrieve)

        used = set()
        semantic_lines = []
        for idx in idxs[0]:
            sender, msg = semantic_history[idx]
            if msg in used:
                continue
            used.add(msg)
            if sender == "user" and idx + 1 < len(semantic_history):
                next_sender, next_msg = semantic_history[idx + 1]
                if next_msg not in used:
                    semantic_lines.append(f"[user]: {msg}")
                    used.add(next_msg)
                    semantic_lines.append(f"[assistant]: {next_msg}")
            elif sender != "user" and idx > 0:
                prev_sender, prev_msg = semantic_history[idx - 1]
                if prev_msg not in used:
                    semantic_lines.append(f"[user]: {prev_msg}")
                    used.add(prev_msg)
                    semantic_lines.append(f"[assistant]: {msg}")
        if semantic_lines and len(semantic_lines) > 0:
            context_lines.append(
                f"  - Here are the {len(semantic_lines)//2} most relevant previous message exchanges:"
            )
            context_lines.extend(semantic_lines)
            context_lines.append("")
            context["middle_term_memory"] = semantic_lines

    # Knowledge Base Context - only if strategy allows and LLM is attached to KB
    if llm.is_attached_to_kb and (
        strategy["use_kb_basic"] or strategy["use_kb_enhanced"]
    ):
        try:
            # Use enhanced KB retrieval with more chunks if strategy allows
            kb_top_k = strategy["kb_top_k"]
            kb_context = get_relevant_texts_from_kb(
                query=query, llm=llm, db=db, kb_top_k=kb_top_k
            )

            if not kb_context:
                logger.info("No relevant texts found in Knowledge Base")
            else:
                context_prefix = "\n\nAlso: You are attached to a Knowledge Base."
                if strategy["use_kb_enhanced"]:
                    context_prefix += (
                        " Here is detailed context you need to know for this query:\n"
                    )
                else:
                    context_prefix += " Here is basic context for this query:\n"

                context_lines.append(context_prefix + "\n".join(kb_context))
                context["kb_context"] = kb_context

        except Exception as e:
            logger.exception("Failed to retrieve Knowledge Base context")
            raise HTTPException(
                status_code=500, detail=f"Knowledge Base retrieval error: {str(e)}"
            )

    # Short-term memory (Recent messages) - only if strategy allows
    if strategy["use_short_term_memory"]:
        recent = (
            conversation_history[-n_recent:]
            if len(conversation_history) >= n_recent
            else conversation_history
        )
        if recent:
            context_lines.append(
                f"  - Here are the {len(recent)} most recent messages:"
            )
            for sender, msg in recent:
                role = "[user]" if sender == "user" else "[assistant]"
                context_lines.append(f"{role}: {msg}")

    if context_lines and len(context_lines) > 0:
        context["context_str"] = (
            "Here is context about the conversation you had so far:\n\n"
            + "\n".join(context_lines)
        )

    return context


@router.post("/{conversation_id}/generate_title")
async def generate_title(
    conversation_id: int,
    payload: ConversationQuery,
    db: Session = Depends(get_db),
):
    """Generate a title for the conversation based on the first message."""

    logger.info("Generating title for conversation %s", conversation_id)

    conversation = (
        db.query(Conversation).filter(Conversation.id == conversation_id).first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    llm = db.query(Llm).filter(Llm.id == conversation.llm_id).first()
    if not llm:
        raise HTTPException(status_code=404, detail="LLM not found")
    model_type = llm.type
    try:
        model, tokenizer = vars.LLM_Engine.get_model_and_tokenizer(llm_id=llm.id, llm_local_path=llm.link)
    except Exception as e:
        logger.exception("Failed to load model or tokenizer: %s", e)
        raise HTTPException(status_code=500, detail=f"Model loading error: {str(e)}")

    try:
        # For Mistral we avoid system role because its chat template requires strict user/assistant alternation.
        # We embed the instructions + user query into a single user message.
        if model_type == "mistral":
            merged_title_prompt = (
                "You are a TITLE generator. Produce ONLY a very short title (2–4 words maximum).\n"
                "Rules: only the title text; Title Case; no question mark; no quotes; no emojis; no hashtags; no code; no trailing punctuation; never answer the question; if empty/URL/noise => output nothing.\n"
                f"User message: {payload.question}\n"
                "Do not answer the question, only create a relevant title. Do NOT add quotes around the title.\n"
                "Examples (user question -> title):\n"
                "give me pizza recipe -> Pizza Recipe\n"
                "google founding team members -> Google Founding Team\n"
                "what's the capital of japan -> Japan Capital\n"
                "female of the pig ->  Pig Female Name\n"
            )
            full_title_generation_prompt = [{"role": "user", "content": merged_title_prompt}]
            logger.info(
                "[TitleGen] conversation_id=%s model_type=%s (mistral merged)\n%s",
                conversation_id,
                model_type,
                merged_title_prompt[:400],
            )
        else:
            system_title_generation_prompt = (
                "You are a very-short-title generator. Return ONLY a concise title. "
                "No punctuation (except apostrophes in possessives), no quotes, no hashtags, no emojis, no trailing filler words. "
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
            user_title_generation_prompt = f"""Create a 2-to-4-word title for:\n{payload.question}"""
            merged_title_prompt = f"{system_title_generation_prompt}\n\n{user_title_generation_prompt}"
            full_title_generation_prompt = [{"role": "user", "content": merged_title_prompt}]
            logger.info(
                "[TitleGen] conversation_id=%s model_type=%s (merged prompt)\n%s",
                conversation_id,
                model_type,
                merged_title_prompt[:400],
            )
        logger.debug("[TitleGen] full messages payload: %s", full_title_generation_prompt)

    except Exception as e:
        logger.exception("Failed to tokenize prompt")
        raise HTTPException(status_code=500, detail=f"Tokenization error: {str(e)}")

    async def title_stream():
        generated_title = ""
        try:
            # Early return if user content is empty or whitespace
            if not payload.question or payload.question.strip() == "":
                conversation.name = "New Conversation"
                db.add(conversation)
                db.commit()
                return
            # Adjust generation hyperparams for Mistral to reduce drift into full answers.
            # Preprocessing-only control via generation params (no downstream filtering)
            temp = 0.5 if model_type == "mistral" else 1.0
            nucleus = 0.9 if model_type == "mistral" else 0.95
            max_tok = 12 if model_type == "mistral" else 12
            for new_text in vars.LLM_Engine.generate_stream(
                model=model,
                tokenizer=tokenizer,
                prompt=full_title_generation_prompt,
                temperature=temp,
                top_p=nucleus,
                max_tokens=max_tok,
                repetition_penalty=1.2,
            ):
                logger.info(f"[TitleGen Stream] token: {new_text}")
                generated_title += new_text
                yield new_text
        except Exception as e:
            # Do not raise after partial streaming; just log and fallback.
            logger.exception("Title streaming failed")
        finally:
            final_title = generated_title if generated_title is not None else ""
            # Save exactly what was streamed (no downstream post-processing)
            conversation.name = final_title if final_title != "" else "New Conversation"
            db.add(conversation)
            db.commit()
            logger.info("Title generated and saved: %s", conversation.name) 
    return StreamingResponse(title_stream(), media_type="text/plain")


@router.post("/{conversation_id}/query")
async def query_and_respond(
    conversation_id: int,
    payload: ConversationQuery,
    db: Session = Depends(get_db),
):
    logger.info("Payload reçu : %s", payload.dict())
    user_prompt = payload.custom_prompt
    conversation = (
        db.query(Conversation).filter(Conversation.id == conversation_id).first()
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    user_message = Message(
        conversation_id=conversation_id, sender="user", content=payload.question
    )
    db.add(user_message)
    db.flush()

    conversation.last_message_time = datetime.now()
    db.commit()

    llm = db.query(Llm).filter(Llm.id == conversation.llm_id).first()
    if not llm:
        raise HTTPException(status_code=404, detail="LLM not found")
    model_type = llm.type

    # Get prompting strategy based on model size
    param_size = llm.param_size
    strategy = get_prompting_strategy(param_size)
    logger.info(f"Using prompting strategy for {param_size}B model: {strategy}")

    # Context Fetching
    try:
        full_msgs_history = get_conversation_history(db, conversation_id)
        if full_msgs_history[-1][0] == "user":
            full_msgs_history.pop(-1)
        if not full_msgs_history or full_msgs_history == []:
            logger.info(
                "No previous messages in conversation, skipping context retrieval"
            )

        logger.info(f"Retrieving context for conversation {conversation_id}")
        start = datetime.now()
        context = retrieve_context(
            payload.question,
            full_msgs_history,
            conversation_id,
            llm=llm,
            db=db,
            strategy=strategy,
            n_last_turns=payload.n_last_turns_to_get or strategy["max_history_turns"],
            model_type=model_type,
        )
        context_str, long_term_memory, middle_term_memory, kb_context = (
            context["context_str"],
            context["long_term_memory"],
            context["middle_term_memory"],
            context["kb_context"],
        )

        messages_starred = []
        if full_msgs_history:
            for msg in full_msgs_history:
                msg_starred_object = (
                    db.query(Message)
                    .filter(Message.content == msg[1], Message.starred == True)
                    .first()
                )
                if msg_starred_object:
                    messages_starred.append(msg_starred_object.content)
            if len(messages_starred) == 0:
                messages_starred = None
    except Exception as e:
        logger.exception("Failed to retrieve context")
        raise HTTPException(
            status_code=500, detail=f"Context retrieval error: {str(e)}"
        )

    # Prompt construction - respects strategy
    # Separate components for strategic placement:
    # - System prompt: assistant's identity (goes at the beginning)
    # - Custom prompt: task-specific instructions (goes with current question)
    # - KB context: relevant knowledge (goes with current question)
    # - Long-term memory: conversation summary (goes at the beginning)

    custom_prompt = ""
    kb_prompt = ""
    mtm_prompt = ""

    # System prompt: defines the assistant's identity based on model size category
    size_category = strategy.get("system_prompt_size_category", "medium")
    sys_prompt = build_system_prompt(
        model_name=llm.name,
        size_category=size_category,
        long_term_memory=(
            long_term_memory if long_term_memory and long_term_memory != "" else None
        ),
        starred_messages=(
            messages_starred if messages_starred and len(messages_starred) > 0 else None
        ),
    )

    logger.info(
        f"Using system prompt for size category '{size_category}': {sys_prompt[:100]}..."
    )

    # Relevant previous messages
    if middle_term_memory and len(middle_term_memory) > 0:
        mtm_prompt = "\nThese previous messages could be useful:\n" + "\n".join(
            middle_term_memory
        )

    # Custom prompt: task-specific instructions (will be added to current question)
    if strategy["use_custom_prompt"] and payload.custom_prompt:
        custom_prompt = f"\nAdditional instructions: {payload.custom_prompt}"

    # KB context: relevant knowledge for the current query (will be added to current question)
    if kb_context and kb_context != "":
        kb_prompt = f"\nRelevant context from Knowledge Base:\n" + "\n".join(kb_context)

    final_prompt = []

    # Build conversation history - limited by strategy
    if len(full_msgs_history or []) > 0:
        # Use strategy's max_history_turns instead of hardcoded value
        # max_history_turns = number of conversation turns (each turn = user + assistant)
        max_turns = strategy["max_history_turns"]

        # Calculate how many messages to include (each turn = 2 messages)
        max_messages = max_turns * 2

        # Start from the last max_messages in history
        if len(full_msgs_history) > max_messages:
            start_idx = len(full_msgs_history) - max_messages
        else:
            start_idx = 0

        # Ensure we start on a user message (even index)
        if start_idx % 2 != 0:
            start_idx += 1

        logger.info(
            f"Including {max_turns} conversation turn(s) starting from index {start_idx}"
        )
        logger.info(
            f"Total history length: {len(full_msgs_history)}, including from index {start_idx}"
        )

        for i in range(start_idx, len(full_msgs_history), 2):
            if i < len(full_msgs_history):
                final_prompt.append(
                    {"role": "user", "content": full_msgs_history[i][1]}
                )
            if i + 1 < len(full_msgs_history):
                final_prompt.append(
                    {"role": "assistant", "content": full_msgs_history[i + 1][1]}
                )

    # Add current question with custom prompt and KB context fused into it
    current_question = payload.question

    # Build the current question with relevant context
    # Order: KB context (if any) -> Custom instructions (if any) -> Question
    question_with_context = ""

    if mtm_prompt:
        question_with_context += mtm_prompt + "\n\n"

    if kb_prompt:
        question_with_context += kb_prompt + "\n\n"

    if custom_prompt:
        question_with_context += custom_prompt + "\n\n"

    question_with_context += payload.question
    current_question = question_with_context

    if len(final_prompt) == 0:
        # No history: merge system prompt into the first (and only) user message
        if sys_prompt:
            current_question = f"{sys_prompt}\n\n{current_question}"
    else:
        # Has history: prepend system prompt to first message in final_prompt
        if sys_prompt:
            final_prompt[0]["content"] = f"{sys_prompt}\n\n{final_prompt[0]['content']}"

    final_prompt.append({"role": "user", "content": current_question})
    logger.info("Final prompt to model:\n%s", final_prompt)

    # Model Loading
    try:
        model, tokenizer = vars.LLM_Engine.get_model_and_tokenizer(llm_id=llm.id, llm_local_path=llm.link)
    except Exception as e:
        logger.exception("Failed to load model or tokenizer: %s", e)
        raise HTTPException(status_code=500, detail=f"Model loading error: {str(e)}")

    async def assistant_response_token_stream():
        assistant_response = ""
        start = datetime.now()
        logger.info(
            f"Generating response from MLX model for prompt: {payload.question}"
        )
        try:
            for text in vars.LLM_Engine.generate_stream(
                model=model,
                tokenizer=tokenizer,
                prompt=final_prompt,
                max_tokens=payload.max_new_tokens or 1024,
                temperature=payload.temperature,
                top_p=payload.top_p,
                repetition_penalty=1.2,
                repetition_context_size=payload.max_new_tokens or 1024,
            ):
                assistant_response += text
                # logger.info(f"Yielding token: {text}")
                yield text

        except Exception as e:
            logger.exception("Streaming failed")
            error_msg = "[ERROR_MESSAGE_SYSTEM] Generation failed due to an error. Please try again or contact developer team."
            assistant_response = error_msg
            yield error_msg
            raise HTTPException(status_code=500, detail=f"Streaming error: {str(e)}")
        finally:
            # Store the response (either successful or error message)
            assistant_message = Message(
                conversation_id=conversation_id,
                sender="llm",
                content=assistant_response.strip(),
            )
            db.add(assistant_message)
            conversation.last_message_time = datetime.now()
            db.commit()
            logger.info(f"Response generated in {datetime.now() - start} seconds")

            logger.info("Generation finished")

    return StreamingResponse(assistant_response_token_stream(), media_type="text/plain")


@router.post("/delete_bulk")
async def delete_bulk(
    payload: ConversationDeleteBulk,
    db: Session = Depends(get_db),
):
    """Delete multiple conversations by their IDs (body JSON)."""
    try:
        conversation_ids = payload.conversation_ids

        global _conversation_summary_cache
        for conv_id in conversation_ids:
            if conv_id in _conversation_summary_cache:
                del _conversation_summary_cache[conv_id]
                logger.info(
                    f"Cleared summary cache for deleted conversation {conv_id}"
                )

        db.query(Conversation).filter(Conversation.id.in_(conversation_ids)).delete(
            synchronize_session=False
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not delete conversations: {str(e)}",
        )
    return {"message": "Conversations deleted successfully"}


@router.post("/{conversation_id}/store_error_message")
async def store_error_message(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    """Store an error message in the conversation when generation fails."""

    conversation = (
        db.query(Conversation).filter(Conversation.id == conversation_id).first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Create an error message from the assistant
    error_message = Message(
        conversation_id=conversation_id,
        sender="llm",
        content="[ERROR_MESSAGE_SYSTEM] I apologize, but I encountered an error while generating a response. Please try asking your question again.",
    )

    try:
        db.add(error_message)
        conversation.last_message_time = datetime.now()
        db.commit()

        logger.info(f"Stored error message for conversation {conversation_id}")
        vars.LLM_Engine.cleanup()
        return {
            "message": "Error message stored successfully",
            "error_message_id": error_message.id,
        }
    except Exception as e:
        db.rollback()
        logger.exception(
            f"Failed to store error message for conversation {conversation_id}"
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to store error message: {str(e)}"
        )


@router.post("/star_message")
async def star_message(
    message: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    """Star a message in the conversation."""

    message = db.query(Message).filter(Message.content == message).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message to star not found")

    message.starred = True
    try:
        db.commit()
        logger.info(f"Message {message.id} starred successfully.")
        return {"state": "success", "message": "Message starred successfully"}
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to star message.")
        raise HTTPException(status_code=500, detail=f"Failed to star message: {str(e)}")


@router.post("/unstar_message")
async def unstar_message(
    message: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    """Unstar a message in the conversation."""

    message = db.query(Message).filter(Message.content == message).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message to unstar not found")

    message.starred = False
    try:
        db.commit()
        logger.info(f"Message {message.id} unstarred successfully.")
        return {"state": "success", "message": "Message unstarred successfully"}
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to unstar message.")
        raise HTTPException(
            status_code=500, detail=f"Failed to unstar message: {str(e)}"
        )
