from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.Conversation import Conversation
from app.models.Message import Message
from app.schemas.message_schemas import MessageCreate, MessageResponse
from datetime import datetime
from transformers import pipeline, AutoTokenizer
import logging

def init_summarizer():
    """
    Initialize the summarization pipeline.
    This function is called once to set up the summarizer.
    """
    global summarizer
    try:
        if summarizer is not None:
            logging.info("Summarizer already initialized, skipping re-initialization.")
            return
        model = AutoTokenizer.from_pretrained("t5-small", cache_dir="data/models_cache")
        tokenizer = AutoTokenizer.from_pretrained("t5-small", cache_dir="data/models_cache")
        summarizer = pipeline("summarization", model=model, tokenizer=tokenizer, device=0)
        logging.info("Summarizer initialized successfully.")
    except Exception as e:
        logging.error(f"Error initializing summarizer: {e}")
        raise e
    
summarizer = None
router = APIRouter()

@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_messages_by_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """
    Fetch all messages for a specific conversation.
    """
    messages = db.query(Message).filter(Message.conversation_id == conversation_id).all()
    return messages

@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def add_message_to_conversation(conversation_id: int, message: MessageCreate, db: Session = Depends(get_db)):
    """
    Add a new message to a specific conversation and update the last_message_time.
    """
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    new_message = Message(conversation_id=conversation_id, **message.dict())
    db.add(new_message)
    db.flush()

    count = db.query(Message).filter(Message.conversation_id == conversation_id).count()
    if count==1:
        seuil = 10
        words = new_message.content.strip().split()

        if len(words)<seuil:
            conversation.name = new_message.content.strip()
        else : 
            init_summarizer()
            prompt=("Very short title, don't exceed 10 words : \n" + new_message.content)
            summary = summarizer(prompt, max_length=10, min_length=5, do_sample=False)[0]["summary_text"]
            conversation.name = summary
        logging.info("Premier message résumé pour le titre : %s", conversation.name)

    conversation.last_message_time = datetime.utcnow()

    db.commit()
    db.refresh(new_message)
    return new_message

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

