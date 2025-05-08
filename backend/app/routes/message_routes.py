from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models.Conversation import Conversation
from ..models.Message import Message
from ..schemas.message_schemas import MessageCreate, MessageResponse
from datetime import datetime

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

