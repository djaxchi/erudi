from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import basic_routes, llm_routes, conversation_routes, message_routes, bd_routes, hardware_routes, folder_routes
from .database import Base, engine
from .models.Llm import Llm
from sqlalchemy.orm import Session
from .database import SessionLocal
from pydantic import BaseModel
import logging
from .models.Conversation import Conversation
from .models.Message import Message

async def createTables():
    # Create all tables in the database
    Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    await createTables()

    db: Session = SessionLocal()
    
    try:
        if db.query(Llm).first() is None:

            llm1 = Llm(name="Mistral-7B : Base Model", local=0, link="mistralai/Mistral-7B-Instruct-v0.3")
            db.add_all([llm1])
            db.commit()
            logging.info("Startup: Mistral LLM created successfully in DB.")
        else:
            logging.info("Startup: Mistral LLM already exists in DB, skipping creation.")
    except Exception as e:
        logging.error(f"Error creating first LLM: {e}")
        db.rollback()
    finally:
        db.close()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(basic_routes.router)
app.include_router(llm_routes.router)
app.include_router(conversation_routes.router)
app.include_router(message_routes.router)
app.include_router(bd_routes.router)
app.include_router(hardware_routes.router)
app.include_router(folder_routes.router)
