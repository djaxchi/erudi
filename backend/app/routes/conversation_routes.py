from app.schemas.message_schemas import MessageCreate, MessageResponse
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from transformers import StoppingCriteria, StoppingCriteriaList
import torch
from datetime import datetime
from transformers import AutoTokenizer, AutoModelForCausalLM, TextIteratorStreamer
import logging
from typing import List
from app.database import get_db
from app.models.Conversation import Conversation
from app.models.Llm import Llm
from app.models.Message import Message
from app.routes.message_routes import add_message_to_conversation
from app.schemas.conversation_schemas import ConversationCreate, ConversationDeleteBulk, ConversationQuery, ConversationQueryResponse, ConversationResponse, ConversationUpdate, ConversationWithMessagesResponse
import threading
from fastapi.responses import StreamingResponse
from faiss import IndexFlatL2
from sentence_transformers import SentenceTransformer
import numpy as np
from app.prompting.builder import build_default_prompt, build_custom_prompt
import re
import time

loaded_model = None
current_tokenizer  = None
loaded_model_id = None
embedder = None

router = APIRouter()

class StopOnEndToken(StoppingCriteria):
    def __init__(self, end_token_id: int):
        self.end_token_id = end_token_id
    def __call__(self, input_ids, scores, **kwargs):
        # arrête si le dernier token généré est <|end|>
        return input_ids[0, -1].item() == self.end_token_id



@router.get("/conversations", response_model=List[ConversationResponse])
async def get_all_conversations(db: Session = Depends(get_db)):
    """
    Fetch all conversations.
    """
    try:
        conversations = db.query(Conversation).all()
        return conversations
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.get("/conversations/{conversation_id}", response_model=ConversationWithMessagesResponse)
async def get_conversation_by_id(conversation_id: int, db: Session = Depends(get_db)):
    """
    Fetch a single conversation by its ID, including messages.
    """
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation

@router.post("/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
):
    """Create a new conversation for a specific LLM (body JSON)."""

    conversation = Conversation(llm_id=payload.llm_id, name="New Conversation")
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

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """
    Delete a conversation by its ID.
    """
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conversation)
    db.commit()
    return {"message": "Conversation deleted successfully"}

@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
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

def get_conversation_history(db: Session, conversation_id: int):
    try:
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.timestamp.asc()).all()
        
        formatted_messages = []
        if len(messages) == 0 or len(messages) == 1:
            return formatted_messages
        for msg in messages:
            # prefix = "[USER]" if msg.sender == "user" else "[ASSISTANT]"
            formatted_messages.append(f"{msg.content}")
        
        return formatted_messages
    except Exception as e:
        logging.exception(f"Error retrieving conversation history: {e}")
        return []

def retrieve_context(query: str, conversation_history: List[str], top_k=3):

    def get_embedder():
        global embedder
        if embedder is None:
            logging.info("Loading the Embedder")
            start = datetime.now()
            embedder = SentenceTransformer("sentence-transformers/distiluse-base-multilingual-cased-v2")
            logging.info(f"Embedder loaded in {datetime.now() - start} seconds")
        return embedder

    if conversation_history == []:
        return ""
   
    embedder = get_embedder()
   
    query_embedding = embedder.encode(query, convert_to_tensor=True)
   
    message_embeddings = embedder.encode(conversation_history, convert_to_tensor=False)
   
    dimension = len(message_embeddings[0])
    index = IndexFlatL2(dimension)
    index.add(np.array(message_embeddings))
   
    distances, indices = index.search(np.array([query_embedding.cpu().numpy()]), k=min(top_k, len(conversation_history)))
   
    semantic_context  = "\n".join([conversation_history[idx] for idx in indices[0]])
   
    last_two_turns = conversation_history[-4:]
    recency_context = "\n".join(last_two_turns)

    if semantic_context:
        relevant_context = semantic_context + "\n\n" + recency_context
    else:
        relevant_context = recency_context

    return relevant_context


@router.post("/conversations/{conversation_id}/query", response_model=MessageResponse)
async def query(
    conversation_id: int,
    payload: ConversationQuery,
    db: Session = Depends(get_db),
):  
    logging.info("Payload reçu : %s", payload.dict())
    user_prompt = payload.custom_prompt
    device = "cuda" if torch.cuda.is_available() else "cpu"
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )
     
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    llm = db.query(Llm).filter(Llm.id == conversation.llm_id).first()
    if not llm:
        raise HTTPException(status_code=404, detail="LLM not found")
    
    global loaded_model, current_tokenizer, loaded_model_id

    try:
        if loaded_model_id != llm.id or loaded_model is None:
            start = datetime.now()
            logging.info(f"Loading model {llm.id} from {llm.link}")
            loaded_model = AutoModelForCausalLM.from_pretrained(
                llm.link, local_files_only=True, torch_dtype=torch.float16
            )
            current_tokenizer = AutoTokenizer.from_pretrained(llm.link, local_files_only=True)
            loaded_model_id = llm.id
            loaded_model.eval()
            loaded_model.to(device)
            logging.info(f"Model {llm.id} loaded in {datetime.now() - start} seconds")
        else:
            logging.info(f"Model {llm.id} already loaded")
            loaded_model.eval()
            loaded_model.to(device)
    except Exception as e:
        logging.exception("Failed to load model or tokenizer")
        raise HTTPException(status_code=500, detail=f"Model loading error: {str(e)}")

    try :
        conversation_history = get_conversation_history(db, conversation_id)
        if not conversation_history:
            relevant_context = ""
            logging.info("No previous messages in conversation, skipping context retrieval")
        else:
            logging.info(f"Retrieving context for conversation {conversation_id}")
            start = datetime.now()
            relevant_context = retrieve_context(payload.question, conversation_history)
            logging.info(f"Found relevant context: {relevant_context[:100]}... in {datetime.now() - start} seconds")
    except Exception as e:
        logging.exception("Failed to retrieve context")
        raise HTTPException(status_code=500, detail=f"Context retrieval error: {str(e)}")
    

    lang = payload.language
    max_tokens_out = payload.max_new_tokens or 3074

    prompt_text = build_default_prompt(
            question=payload.question,
            history=conversation_history,
            context=relevant_context,
            language=lang,
            max_tokens=max_tokens_out
        )

    if payload.custom_prompt:
        logging.info("➡️ Rendering custom prompt via Jinja")
        prompt_text_customized = build_custom_prompt(
            payload.custom_prompt,
            payload.question,
            conversation_history,
            relevant_context,
            lang
        )
        prompt_text = ( prompt_text + "\n Instructions Utilisateur Personnalisées : " + prompt_text_customized )


    logging.info("Final prompt to model:\n%s", prompt_text)


    try:
        input_ids = current_tokenizer.encode(prompt_text, return_tensors="pt").to(device)
        end_ids = current_tokenizer.encode("<|end|>", add_special_tokens=False)
        stop_crit = StoppingCriteriaList([StopOnEndToken(end_ids[-1])])
    except Exception as e:
        logging.exception("Failed to tokenize prompt")
        raise HTTPException(status_code=500, detail=f"Tokenization error: {str(e)}")
    
    streamer = TextIteratorStreamer(current_tokenizer, skip_prompt=True, skip_special_tokens=True)

    generation_kwargs = dict(
        input_ids=input_ids,
        streamer=streamer,
        max_new_tokens=max_tokens_out,
        temperature=payload.temperature or 0.9,
        top_p= payload.top_p or 0.9,
        do_sample=True,
        num_beams=1,
        pad_token_id=current_tokenizer.eos_token_id,
        stopping_criteria=stop_crit
    )

    logging.info("Generation kwargs for Mistral : %s, %s, %s", generation_kwargs["max_new_tokens"], generation_kwargs["temperature"], generation_kwargs["top_p"])

    def run_generation():
        logging.info(f"Generating response for conversation {conversation_id} with question: {payload.question}")
        try:
            with torch.no_grad():
                loaded_model.generate(**generation_kwargs)
        except Exception as e:
            logging.exception(f"Generation failed : {e}")
            raise HTTPException(status_code=500, detail=f"Generation error: {str(e)}")

    thread = threading.Thread(target=run_generation)
    thread.start()

    async def token_stream():
        try:
            for new_text in streamer:
                cleand_out_token = re.sub(r"<\|/?(?:assistant|system|user|end)\|>", "", new_text)
                logging.info(f"Yielding token: {cleand_out_token}")
                yield cleand_out_token
        except Exception as e:
            logging.exception("Streaming failed")
            raise HTTPException(status_code=500, detail="Streaming failed")
        finally:
            thread.join()
            logging.info("Generation thread finished")
        
    return StreamingResponse(token_stream(), media_type="text/plain")

@router.post("/conversations/delete_bulk")
async def delete_bulk(
    payload: ConversationDeleteBulk,
    db: Session = Depends(get_db),
):
    """Delete multiple conversations by their IDs (body JSON)."""
    try:
        conversation_ids = payload.conversation_ids
        db.query(Conversation).filter(Conversation.id.in_(conversation_ids)).delete(synchronize_session=False)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not delete conversations: {str(e)}",
        )
    return {"message": "Conversations deleted successfully"}