from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.Llm import Llm
from app.models.Conversation import Conversation
from app.models.Message import Message

# routes only for testing purposes

router = APIRouter(prefix="/db", tags=["Database"])

@router.post("/reset")
async def reset_database(db: Session = Depends(get_db)):
    """
    Reset the database by deleting all data.
    """
    try:
        db.query(Message).delete()
        db.query(Conversation).delete()
        db.query(Llm).delete()
        db.commit()
        return {"message": "Database reset successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error resetting database: {str(e)}")

@router.post("/fill")
async def fill_database_with_test_data(db: Session = Depends(get_db)):
    """
    Fill the database with test data (models, conversations, and messages).
    """
    try:
        # Add test LLMs
        llm1 = Llm(name="Test Model 1", local=1, link="/models/test_model_1")
        llm2 = Llm(name="Test Model 2", local=0, link="https://huggingface.co/test_model_2")
        llm3 = Llm(name="Mistral-7B : Base Model", local=0, link="mistralai/Mistral-7B-Instruct-v0.3")
        db.add_all([llm1, llm2, llm3])
        db.commit()

        # Add a test conversation for LLM 1
        conversation1 = Conversation(llm_id=llm1.id)
        db.add(conversation1)
        db.commit()

        # Add test messages for the conversation
        message1 = Message(conversation_id=conversation1.id, sender="user", content="Hello, Model 1!")
        message2 = Message(conversation_id=conversation1.id, sender="llm", content="Hello, User!")
        db.add_all([message1, message2])
        db.commit()

        return {"message": "Database filled with test data successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error filling database: {str(e)}")