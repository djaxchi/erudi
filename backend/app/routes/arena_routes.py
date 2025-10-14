from datetime import datetime
import logging
from app.schemas.arena_schemas import ArenaQueryPayload
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.Llm import Llm
from app.utils.inference_utils import ModelManager, get_prompting_strategy, get_relevant_texts_from_kb, build_system_prompt

router = APIRouter(prefix="/arena", tags=["arena"])

@router.post("/{llm_id}/query")
async def query_arena(
    llm_id: int,
    payload: ArenaQueryPayload,
    db: Session = Depends(get_db)
):
    """
    Stateless arena query optimized for Gemma3:
    - llm_id: ID du modèle
    - payload: { question, temperature?, topP?, maxNewTokens?, customPrompt? }
    """
    if not payload.question:
        raise HTTPException(status_code=400, detail="Missing 'question'")
        
    logging.info(f"Querying LLM {llm_id} from DB")
    llm = db.query(Llm).filter(Llm.id == llm_id).first()
    logging.info(f"Querying LLM from DB finished")
    
    if not llm:
        raise HTTPException(status_code=404, detail="LLM not found")

    # Get prompting strategy based on model size
    param_size = llm.param_size if hasattr(llm, 'param_size') and llm.param_size else 2
    strategy = get_prompting_strategy(param_size)
    logging.info(f"Using prompting strategy for {param_size}B model: {strategy}")

    custom_prompt = ""
    kb_prompt = ""

    if llm.is_attached_to_kb and strategy["use_kb_context"]:
        try:
            relevant_texts = get_relevant_texts_from_kb(payload.question, llm, db, kb_top_k=strategy["kb_top_k"])
            if relevant_texts:
                kb_prompt = "Relevant context from Knowledge Base:\n" + "\n".join(relevant_texts)
        except Exception as e:
            logging.exception("Failed to retrieve Knowledge Base context")
            raise HTTPException(status_code=500, detail=f"Knowledge Base retrieval error: {str(e)}")
    
    # System prompt: defines the assistant's identity based on model size category
    size_category = strategy.get("system_prompt_size_category", "medium")
    sys_prompt = build_system_prompt(
        model_name=llm.name,
        size_category=size_category,
        long_term_memory=None,
        starred_messages=None
    )

    # Custom prompt: task-specific instructions (will be added to current question)
    if strategy["use_custom_prompt"] and payload.custom_prompt:
        custom_prompt = f"\nAdditional instructions: {payload.custom_prompt}"

    final_prompt = []
    
    # Add current question with custom prompt and KB context fused into it
    current_question = payload.question
    
    # Build the current question with relevant context
    # Order: KB context (if any) -> Custom instructions (if any) -> Question
    question_with_context = ""
    
    if kb_prompt and kb_prompt != "":
        question_with_context += kb_prompt + "\n\n"
    
    if custom_prompt and custom_prompt != "":
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
    logging.info("Final prompt to model:\n%s", final_prompt)

    # Model Loading
    try:
        model, tokenizer = ModelManager.get_model_and_tokenizer(llm)
    except Exception as e:
        logging.exception("Failed to load model or tokenizer")
        raise HTTPException(status_code=500, detail=f"Model loading error: {str(e)}")

    async def response_token_stream():
        assistant_response = ""
        start = datetime.now()
        logging.info(f"Generating response from MLX model for prompt: {payload.question}")
        try:
            for new_text in ModelManager.generate_stream(
                model=model,
                tokenizer=tokenizer,
                prompt = final_prompt,
                max_tokens=payload.max_new_tokens or 1024,
                temperature=payload.temperature or 0.1,
                top_p=payload.top_p or 0.5,
                repetition_penalty=1.2,
                repetition_context_size=payload.max_new_tokens or 1024,
                min_new_tokens=5,
                patience=7
            ):
                
                assistant_response += new_text
                # logging.info(f"Yielding token: {new_text}")
                if new_text:
                    yield new_text

        except Exception as e:
            logging.exception("Streaming failed")
            raise HTTPException(status_code=500, detail="Streaming failed")
        finally:
            logging.info("Generation thread finished")
    
    return StreamingResponse(response_token_stream(), media_type="text/plain")
