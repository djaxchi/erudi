from datetime import datetime
import os
from pathlib import Path
import shutil

from app.utils.global_variables_util import BASE_PATH, HF_TOKEN

from app.routes import knowledgeBase_routes
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import basic_routes, llm_routes, conversation_routes, bd_routes, hardware_routes, training_routes, arena_routes
from app.database import Base, engine
from app.models.Llm import Llm
from sqlalchemy.orm import Session
from app.database import SessionLocal
import logging
from app.models.Conversation import Conversation
from app.models.Message import Message
from app.models.TrainingJob import TrainingJob
from app.models.DownloadJob import DownloadJobModel
from app.models.KnowledgeBase import KnowledgeBase
from app.models.VectorStore import VectorStore
from app.models.StaticHardwareInfos import StaticHardwareInfo
from huggingface_hub import HfApi


async def createTables():
    # Create all tables in the database
    Base.metadata.create_all(bind=engine)

async def delete_all_data():
    # Delete all data from the database
    db: Session = SessionLocal()
    try:
        
        models_path = os.path.join(BASE_PATH, "data", "models")
        if os.path.exists(models_path):
            shutil.rmtree(models_path)
        os.makedirs(models_path, exist_ok=True)
        indexes_path = os.path.join(BASE_PATH, "data", "indexes")
        if os.path.exists(indexes_path):
            shutil.rmtree(indexes_path)
        os.makedirs(indexes_path, exist_ok=True)
        db.query(Llm).delete()
        db.query(Conversation).delete()
        db.query(Message).delete()
        db.query(TrainingJob).delete()
        db.query(DownloadJobModel).delete()
        db.query(StaticHardwareInfo).delete()
        db.query(VectorStore).delete()
        db.query(KnowledgeBase).delete()

        db.commit()
        logging.info("All data deleted successfully.")
    except Exception as e:
        logging.error(f"Error deleting data: {e}")
        db.rollback()
    finally:
        db.close()

app = FastAPI()

async def startup_populate_database():

    try:
        api = HfApi(token=HF_TOKEN)
        db: Session = SessionLocal()

        # Populate the database with some base models
        base_mistral_instr = db.query(Llm).filter(Llm.name == "Mistral-7B-Instruct-v0.3").first()
        if not base_mistral_instr:
            base_mistral_instr = Llm(
                    name="Mistral-7B-Instruct-v0.3",  
                    local=0,
                    link="mistralai/Mistral-7B-Instruct-v0.3",
                    type="mistral"
                )
            db.add(base_mistral_instr)
        base_mistral = db.query(Llm).filter(Llm.name == "Mistral-7B-v0.3").first()
        if not base_mistral:
            base_mistral = Llm(
                    name="Mistral-7B-v0.3",  
                    local=0,
                    link="mistralai/Mistral-7B-v0.3",
                    type="mistral"
                )
            db.add(base_mistral)
        base_gemma1B = db.query(Llm).filter(Llm.name == "Gemma-3-1B-it").first()
        if not base_gemma1B:
            base_gemma1B = Llm(
                    name="Gemma-3-1B-it",  
                    local=0,
                    link="google/gemma-3-1b-it",
                    type="gemma"
                )
            db.add(base_gemma1B)
        base_gemma2B = db.query(Llm).filter(Llm.name == "Gemma-2-2B-it").first()
        if not base_gemma2B:
            base_gemma2B = Llm(
                    name="Gemma-2-2B-it",  
                    local=0,
                    link="google/gemma-2-2b-it",
                    type="gemma"
                )
            db.add(base_gemma2B)
        base_gemma4B = db.query(Llm).filter(Llm.name == "Gemma-3-4B-it").first()
        if not base_gemma4B:
            base_gemma4B = Llm(
                    name="Gemma-3-4B-it",  
                    local=0,
                    link="google/gemma-3-4b-it",
                    type="gemma"
                )
            db.add(base_gemma4B)

        
        SKIP_IDS = [
            "mistral-7b-instruct-v0.3",
            "mistral-7b-v0.3",
        ]
        SKIP_TERMS = [
            "gguf","gptq","bnb","4bit","8bit","f16","awq",
            "q4","q5","q6", "q8", "fp8","fp16","fp4","sqft", 'quantized',
            "quant", "quantized", "quantization", "lora", "knut",
            "sft", "int4", "int8", "int16", "int32", "int64",
            "peft", "test"
        ]
        # Populate with some Mistral-7B variant community models
        for m in api.list_models(search="Mistral-7B v0.3", sort="downloads", direction=-1):
            # Skip models that are not relevant (e.g. quantized versions of the same base model, as we already natively quantize) or already exist
            mid = m.modelId.lower()
            mname = mid.split("/")[-1].lower()
            # skip exact matches or any unwanted substring
            if mname in SKIP_IDS or any(term in mid for term in SKIP_TERMS):
                continue

            exists = db.query(Llm).filter_by(link=m.modelId).first()
            if exists:
                continue

            llm_entry = Llm(
                name=m.modelId.split("/")[-1],  
                local=0,
                link=m.modelId,
                type="mistral" if "mistral" in m.modelId.lower() else "gemma"
            )
            db.add(llm_entry)

        for i, m in enumerate(api.list_models(search="Gemma 1B", sort="downloads", direction=-1)):
            if i >= 30:
                break
            # Skip models that are not relevant (e.g. quantized versions of the same base model, as we already natively quantize) or already exist
            mid = m.modelId.lower()
            mname = mid.split("/")[-1].lower()
            # skip exact matches or any unwanted substring
            if mname in SKIP_IDS or any(term in mid for term in SKIP_TERMS):
                continue

            exists = db.query(Llm).filter_by(link=m.modelId).first()
            if exists:
                continue

            llm_entry = Llm(
                name=m.modelId.split("/")[-1],  
                local=0,
                link=m.modelId,
                type="mistral" if "mistral" in m.modelId.lower() else "gemma"
            )
            db.add(llm_entry)
        
        db.commit()


        # Check the DownloadJobs to delete running-but-unfinished jobs (in case of server crash)
        unfinished_jobs = db.query(DownloadJobModel).filter(
            DownloadJobModel.status.in_(["running", "pending"])
        ).all()
        for job in unfinished_jobs:
            job.status = "failed"
            llm = db.query(Llm).filter(Llm.id == job.local_model_id).first()
            if llm:
                llm_path = os.path.join(BASE_PATH, llm.link.lstrip("./"))
                if os.path.exists(llm_path):
                    shutil.rmtree(llm_path, ignore_errors=True)
                db.delete(llm)
            job.error_message = "Downloading was not completed due to application shutdown."
            job.local_model_id = -1
            job.updated_at = datetime.now()
            job.local_model_link = ""
            
            db.commit()
            logging.warning(f"Marked unfinished job {job.id} as failed.")
        db.commit()

        # Check the TrainingJobs to delete running-but-unfinished jobs (in case of server crash)
        unfinished_jobs = db.query(TrainingJob).filter(
            TrainingJob.status.in_(["running", "pending"])
        ).all()
        for job in unfinished_jobs:
            job.status = "failed"
            job.error_message = "Training was not completed due to application shutdown."
            llm = db.query(Llm).filter(Llm.id == job.llm_id).first()
            if llm:
                llm_path = os.path.join(BASE_PATH, llm.link.lstrip("./"))
                if os.path.exists(llm_path):
                    shutil.rmtree(llm_path, ignore_errors=True)
                db.delete(llm)
            job.llm_id = -1
            job.updated_at = datetime.now()
            
            db.commit()
            logging.warning(f"Marked unfinished TrainingJob {job.id} as failed.")
        db.commit()

    except Exception as e:
        logging.error(f"Error during startup event: {e}")
        db.rollback()
        raise
    finally:
        db.close()
        return

@app.on_event("startup")
async def startup_event():
    await createTables()
    # await delete_all_data()
    await startup_populate_database()

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
app.include_router(knowledgeBase_routes.router)