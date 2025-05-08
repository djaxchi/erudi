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

async def createTables():
    # Create all tables in the database
    Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    await createTables()

    db: Session = SessionLocal()

    try:
        # Créer deux LLM
        llm1 = Llm(name="Mistral", local=1, link="data/mistral")
        llm2 = Llm(name="Llama", local=1, link="data/llama")
        db.add_all([llm1, llm2])
        db.commit()

        # Créer une conversation pour chaque LLM
        conv1 = Conversation(llm_id=llm1.id)
        conv2 = Conversation(llm_id=llm2.id)
        db.add_all([conv1, conv2])
        db.commit()

        # Ajouter plusieurs messages à chaque conversation
        messages = [
            Message(conversation_id=conv1.id, sender="user", content="Salut Mistral !"),
            Message(conversation_id=conv1.id, sender="llm", content="Salut utilisateur ! Comment puis-je t’aider ?"),
            Message(conversation_id=conv2.id, sender="user", content="Hey Llama !"),
            Message(conversation_id=conv2.id, sender="llm", content="Bonjour ! Pose-moi une question.")
        ]
        db.add_all(messages)
        db.commit()

        print("Données factices insérées avec succès.")
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
