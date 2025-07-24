import os
import shutil
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import basic_routes, llm_routes, conversation_routes, bd_routes, hardware_routes, training_routes, arena_routes
from .database import Base, engine
from .models.Llm import Llm
from sqlalchemy.orm import Session
from .database import SessionLocal
from pydantic import BaseModel
import logging
from .models.Conversation import Conversation
from .models.Message import Message
from .models.TrainingJob import TrainingJob
from .models.DownloadJob import DownloadJobModel
from huggingface_hub import HfApi

async def createTables():
    # Create all tables in the database
    Base.metadata.create_all(bind=engine)

async def delete_all_data():
    # Delete all data from the database
    db: Session = SessionLocal()
    try:
        
        if os.path.exists("data/models"):
            shutil.rmtree("data/models")
        os.makedirs("data/models", exist_ok=True)
        db.query(Llm).delete()
        db.query(Conversation).delete()
        db.query(Message).delete()
        db.query(TrainingJob).delete()

        db.commit()
        logging.info("All data deleted successfully.")
    except Exception as e:
        logging.error(f"Error deleting data: {e}")
        db.rollback()
    finally:
        db.close()

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    await createTables()
    # await delete_all_data()

    api = HfApi()
    hf_models = api.list_models(search="Mistral-7B v0.3", limit=None)
    

    db: Session = SessionLocal()
    try:
        base_mistral = Llm(
                name="Mistral-7B-Instruct-v0.3",  
                local=0,
                link="mistralai/Mistral-7B-Instruct-v0.3"           
            )
        base_gemma1B = Llm(
                name="Gemma-3-1B-it",  
                local=0,
                link="google/gemma-3-1b-it"           
            )
        base_gemma2B = Llm(
                name="Gemma-2-2B-it",  
                local=0,
                link="google/gemma-2-2b-it"           
            )
        base_gemma4B = Llm(
                name="Gemma-3-4B-it",  
                local=0,
                link="google/gemma-3-4b-it"           
            )
        db.add(base_mistral)
        db.add(base_gemma1B)
        db.add(base_gemma2B)
        db.add(base_gemma4B)

        for m in hf_models:
            if m.modelId == "mistralai/Mistral-7B-Instruct-v0.3":
                continue

            exists = db.query(Llm).filter_by(link=m.modelId).first()
            if exists:
                continue

            llm_entry = Llm(
                name=m.modelId.split("/")[-1],  
                local=0,
                link=m.modelId               
            )
            db.add(llm_entry)
        
        db.commit()
    except Exception as e:
        logging.error(f"Error during startup event: {e}")
        db.rollback()
        raise
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
app.include_router(bd_routes.router)
app.include_router(hardware_routes.router)
app.include_router(training_routes.router)
app.include_router(arena_routes.router)