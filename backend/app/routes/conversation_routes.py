from ..schemas.message_schemas import MessageCreate, MessageResponse
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import torch
from datetime import datetime
from transformers import AutoTokenizer, AutoModelForCausalLM, TextIteratorStreamer
import logging
from typing import List
from ..database import get_db
from ..models.Conversation import Conversation
from ..models.Llm import Llm
from ..routes.message_routes import add_message_to_conversation
from ..schemas.conversation_schemas import ConversationCreate, ConversationQuery, ConversationQueryResponse, ConversationResponse, ConversationUpdate, ConversationWithMessagesResponse
import threading
from fastapi.responses import StreamingResponse
    
loaded_model = None
current_tokenizer  = None
loaded_model_id = None

router = APIRouter()

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
    """Update conversation fields (currently only *name*)."""

    conversation = (
        db.query(Conversation).filter(Conversation.id == conversation_id).first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if payload.name != conversation.name:
        conversation.name = payload.name
        try:
            db.commit()
            db.refresh(conversation)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not update conversation: {str(e)}",
            )

    return conversation

@router.post("/conversations/{conversation_id}/query", response_model=MessageResponse)
async def query(
    conversation_id: int,
    payload: ConversationQuery,
    db: Session = Depends(get_db),
):  
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

    
    max_tokens = 10000
    model_temperature = 0.5
    system_instruction = (
        "You are an intelligent, polite, and helpful conversational assistant."
        "You can answer all types of questions: general knowledge, emotions, advice, or technical topics."
        "You automatically adapt to the language used by the user."
        "When asked who you are, you simply explain that you are a virtual assistant designed to help."
        "You do not provide false information: if you don't know, you say so."
        "You express yourself naturally and fluently, as in a real conversation."
        "If you cannot answer a question, simply say that you don't know."
        f"You have a total of {max_tokens} tokens to respond, take this into account and do not generate more that this."
        "The user's instruction is the following :"
    )
    
    full_prompt = f"[INST] {system_instruction}\n{payload.question} [/INST]"

    try:
        input_ids = current_tokenizer.encode(full_prompt, return_tensors="pt").to(device)
    except Exception as e:
        logging.exception("Failed to tokenize prompt")
        raise HTTPException(status_code=500, detail=f"Tokenization error: {str(e)}")
    
    streamer = TextIteratorStreamer(current_tokenizer, skip_prompt=True, skip_special_tokens=True)

    generation_kwargs = dict(
        input_ids=input_ids,
        streamer=streamer,
        max_new_tokens=max_tokens,
        temperature=model_temperature,
        top_p=0.9,
        do_sample=True,
        num_beams=1,
        pad_token_id=current_tokenizer.eos_token_id,
    )

    def run_generation():
        logging.info(f"Generating response for conversation {conversation_id} with question: {payload.question}")
        try:
            with torch.no_grad():
                loaded_model.generate(**generation_kwargs)
        except Exception as e:
            logging.exception(f"Generation failed : {e}")

    thread = threading.Thread(target=run_generation)
    thread.start()

    async def token_stream():
        try:
            for new_text in streamer:
                logging.info(f"Streamed chunk: {new_text}")
                yield new_text
        except Exception as e:
            logging.exception("Streaming failed")
            raise HTTPException(status_code=500, detail="Streaming failed")
        
    return StreamingResponse(token_stream(), media_type="text/plain")
