from ..schemas.message_schemas import MessageCreate, MessageResponse
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from transformers import StoppingCriteria, StoppingCriteriaList
import torch
from datetime import datetime
from transformers import AutoTokenizer, AutoModelForCausalLM
import logging
from typing import List
from ..database import get_db
from ..models.Conversation import Conversation
from ..models.Llm import Llm
from ..routes.message_routes import add_message_to_conversation
from ..schemas.conversation_schemas import ConversationCreate, ConversationQuery, ConversationQueryResponse, ConversationResponse, ConversationUpdate, ConversationWithMessagesResponse
from ..prompting.builder import build_prompt
import re

loaded_model = None
current_tokenizer  = None
loaded_model_id = None

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

    if loaded_model_id != llm.id or loaded_model is None:
        start = datetime.now()
        logging.info(f"Loading model {llm.id} from {llm.link}")
        loaded_model = AutoModelForCausalLM.from_pretrained(llm.link, local_files_only=True, torch_dtype=torch.float16)
        current_tokenizer = AutoTokenizer.from_pretrained(llm.link, local_files_only=True)
        loaded_model_id = llm.id
        loaded_model.eval()
        loaded_model.to(device)
        logging.info(f"Model {llm.id} loaded successfully in {datetime.now() - start} seconds")
    else:
        logging.info(f"Model {llm.id} already loaded")
        loaded_model.eval()
        loaded_model.to(device)

    lang = payload.language    # "fr"/"en"
    max_tokens_out = payload.max_new_tokens or 512                # ou ce que tu veux
    prompt = build_prompt(
        question=payload.question,
        history=payload.history,
        language=lang,
        max_tokens=max_tokens_out
    )


    start = datetime.now()
    logging.info(f"Generating response for conversation {conversation_id} with question: {payload.question}")
    
    gen_kwargs = {
        "max_new_tokens": max_tokens_out,
        "temperature": payload.temperature or 0.5,
        "top_p": payload.top_p or 0.9,
        "do_sample": True,
        "num_beams": 1,
        "pad_token_id": current_tokenizer.eos_token_id,
    }

    input_ids = current_tokenizer.encode(prompt, return_tensors="pt").to(device)
    end_ids = current_tokenizer.encode("<|end|>", add_special_tokens=False)
    stop_crit = StoppingCriteriaList([StopOnEndToken(end_ids[-1])])


    with torch.no_grad():
        outputs = loaded_model.generate(
            input_ids,
            **gen_kwargs,
            stopping_criteria=stop_crit
        )
        
    response = current_tokenizer.decode(outputs[0][input_ids.shape[1]:], skip_special_tokens=True)

    cleaned_response = re.sub(r"<\|/?(?:assistant|system|user|end)\|>", "", response).strip()

    logging.info(f"Response generated in {datetime.now() - start} seconds")
    if cleaned_response == "":
        raise HTTPException(status_code=500, detail="Empty response from model")
    
    assistantMessage = await add_message_to_conversation(
        conversation_id, 
        MessageCreate(content=cleaned_response, sender="assistant"),
        db
    )

    return assistantMessage