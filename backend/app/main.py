from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import basic_routes, llm_routes, conversation_routes, message_routes, bd_routes, hardware_routes
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
app.include_router(hardware_routes.router)
