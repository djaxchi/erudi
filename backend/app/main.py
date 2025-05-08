from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import basic_routes, llm_routes, conversation_routes, message_routes, bd_routes
from .database import Base, engine
from .models.Llm import Llm
from sqlalchemy.orm import Session
from .database import SessionLocal
from pydantic import BaseModel
import logging
from .models.Conversation import Conversation
from .models.Message import Message

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMCreate(BaseModel):
    name: str
    local: int
    link: str

class conversationCreate(BaseModel):
    llm_id: int
    messages: list

class messageCreate(BaseModel):
    conversation_id: int
    content: str
    sender: str  # "user" or "llm"

async def createTables():
    # Create all tables in the database
    Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    logger.info("Startup event triggered")    
    # Create tables on startup
    await createTables()
    
    # Mock local LLM data to test the database
    db: Session = SessionLocal()

    try:
        # Mock LLM data
        model = LLMCreate(
            name="MockModel",
            local=1,  # 1 for local, 0 for remote
            link="data/mock_model"
        )
        # Add mock LLM to the database
        db_model = Llm(**model.dict())
        db.add(db_model)
        db.commit()
        db.refresh(db_model)
        logger.info(f"Mock LLM added: {db_model}")

        # Create a conversation
        conversation = Conversation(
            llm_id=db_model.id  # Link to the mock LLM
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        logger.info(f"Mock conversation added: {conversation}")

        # Add two messages to the conversation
        message_1 = Message(
            conversation_id=conversation.id,
            sender="user",
            content="Hello, how are you?"
        )
        message_2 = Message(
            conversation_id=conversation.id,
            sender="llm",
            content="I'm just a model, but I'm doing great! How can I assist you?"
        )
        db.add_all([message_1, message_2])
        db.commit()
        logger.info(f"Mock messages added: {message_1}, {message_2}")

    finally:
        # Close the database session
        db.close()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],  # Allow all origins (you can restrict this to specific origins)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(basic_routes.router)
app.include_router(llm_routes.router)
app.include_router(conversation_routes.router)
app.include_router(message_routes.router)
app.include_router(bd_routes.router)
