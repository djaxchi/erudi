from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.Llm import Llm
from ..models.Conversation import Conversation
from ..models.Message import Message

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
        raise HTTPException(
            status_code=500, detail=f"Error resetting database: {str(e)}"
        )


@router.post("/fill")
async def fill_database_with_test_data(db: Session = Depends(get_db)):
    """
    Fill the database with test data (models, conversations, and messages).
    """
    try:
        # Add test LLMs
        llm1 = Llm(name="Test Model 1", local=1, link="/models/test_model_1")
        llm2 = Llm(
            name="Test Model 2", local=0, link="https://huggingface.co/test_model_2"
        )
        llm3 = Llm(
            name="Mistral-7B : Base Model",
            local=0,
            link="mistralai/Mistral-7B-Instruct-v0.3",
        )
        db.add_all([llm1, llm2, llm3])
        db.commit()

        # Add a test conversation for LLM 1
        conversation1 = Conversation(llm_id=llm1.id)
        db.add(conversation1)
        db.commit()

        # Add test messages for the conversation
        message1 = Message(
            conversation_id=conversation1.id, sender="user", content="Hello, Model 1!"
        )
        message2 = Message(
            conversation_id=conversation1.id, sender="llm", content="Hello, User!"
        )
        message3 = Message(
            conversation_id=conversation1.id, sender="user", content="How are you?"
        )
        message4 = Message(
            conversation_id=conversation1.id,
            sender="llm",
            content="I'm just a model, but I'm here to help!",
        )
        message5 = Message(
            conversation_id=conversation1.id,
            sender="llm",
            content="What can I do for you?",
        )
        message6 = Message(
            conversation_id=conversation1.id, sender="user", content="Tell me a joke."
        )
        message7 = Message(
            conversation_id=conversation1.id,
            sender="llm",
            content="Why did the scarecrow win an award? Because he was outstanding in his field!",
        )
        message8 = Message(
            conversation_id=conversation1.id,
            sender="user",
            content="What is the capital of France?",
        )
        message9 = Message(
            conversation_id=conversation1.id,
            sender="llm",
            content="The capital of France is Paris.",
        )
        message10 = Message(
            conversation_id=conversation1.id,
            sender="user",
            content="What is the meaning of life?",
        )
        message11 = Message(
            conversation_id=conversation1.id,
            sender="llm",
            content="The meaning of life is subjective, but many say it's 42.",
        )
        message12 = Message(
            conversation_id=conversation1.id,
            sender="user",
            content="What is the weather like today?",
        )
        message13 = Message(
            conversation_id=conversation1.id,
            sender="llm",
            content="I don't have real-time data, but you can check a weather app for the latest updates.",
        )
        message14 = Message(
            conversation_id=conversation1.id,
            sender="user",
            content="What is the largest mammal?",
        )
        message15 = Message(
            conversation_id=conversation1.id,
            sender="llm",
            content="The largest mammal is the blue whale.",
        )
        message16 = Message(
            conversation_id=conversation1.id,
            sender="user",
            content="What is the speed of light?",
        )
        message17 = Message(
            conversation_id=conversation1.id,
            sender="llm",
            content="The speed of light in a vacuum is approximately 299,792 kilometers per second (or about 186,282 miles per second).",
        )
        db.add_all(
            [
                message1,
                message2,
                message3,
                message4,
                message5,
                message6,
                message7,
                message8,
                message9,
                message10,
                message11,
                message12,
                message13,
                message14,
                message15,
                message16,
                message17,
            ]
        )
        db.commit()

        return {"message": "Database filled with test data successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error filling database: {str(e)}")
