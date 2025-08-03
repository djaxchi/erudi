from datetime import datetime
import os
import shutil

from .utils.hardware_info import get_hardware_eval_for_NVIDIA_CUDA

from .models.StaticHardwareInfos import StaticHardwareInfo
from .routes import knowledgeBase_routes
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import basic_routes, llm_routes, conversation_routes, bd_routes, hardware_routes, training_routes, arena_routes
from app.database import Base, engine
from app.models.Llm import Llm
from app.routes import basic_routes, llm_routes, conversation_routes, bd_routes, hardware_routes, training_routes, arena_routes
from app.database import Base, engine
from app.models.Llm import Llm
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.database import SessionLocal
from pydantic import BaseModel
import logging
from app.models.Conversation import Conversation
from app.models.Message import Message
from app.models.TrainingJob import TrainingJob
from app.models.Conversation import Conversation
from app.models.Message import Message
from app.models.TrainingJob import TrainingJob
from app.models.DownloadJob import DownloadJobModel
from app.models.KnowledgeBase import KnowledgeBase
from app.models.VectorStore import VectorStore
from app.models.StaticHardwareInfos import StaticHardwareInfo

from huggingface_hub import HfApi
from dotenv import load_dotenv

load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")

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
        if os.path.exists("data/indexes"):
            shutil.rmtree("data/indexes")
        os.makedirs("data/indexes", exist_ok=True)
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
    api = HfApi(token=HF_TOKEN)
    db: Session = SessionLocal()


    try:

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
                shutil.rmtree(llm.link, ignore_errors=True)
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
                shutil.rmtree(llm.link, ignore_errors=True)
                db.delete(llm)
            job.llm_id = -1
            job.updated_at = datetime.now()
            
            db.commit()
            logging.warning(f"Marked unfinished TrainingJob {job.id} as failed.")
        db.commit()

        persist_hw_infos = db.query(StaticHardwareInfo).first()
        if not persist_hw_infos:
            hw = get_hardware_eval_for_NVIDIA_CUDA()
            persist_hw_infos = StaticHardwareInfo(
                available_ram_gb=hw.get("available_ram_gb", None),
                disk_total_gb=hw.get("disk_total_gb", None),
                disk_avail_gb=hw.get("disk_avail_gb", None),
                gpu_name=hw.get("gpu_name", "Unknown"),
                cpu_model=hw.get("cpu_model", None),
                vram_total_gb=hw.get("vram_total_gb", None),
                sm_clock_ghz=hw.get("sm_clock_ghz", None),
                mem_clock_mhz=hw.get("mem_clock_mhz", None),
                bus_width_bits=hw.get("bus_width_bits", None),
                mem_bandwidth_gbs=hw.get("mem_bandwidth_gbs", None),
                compute_cap=hw.get("compute_cap", None),
                sm_count=hw.get("sm_count", None),
                cuda_cores_total=hw.get("cuda_cores_total", None),
                fp32_tflops=hw.get("fp32_tflops", None),
                tensor_tflops=hw.get("tensor_tflops", None),
                system_ram_gb=hw.get("system_ram_gb", None),
                cpu_perf_units=hw.get("cpu_perf_units", None),
                pcie_perf_units=hw.get("pcie_perf_units", None),
                cuda_runtime_available=hw.get("cuda_runtime_available", None),
                cuda_toolkit_path=hw.get("cuda_toolkit_path", None),
                global_inference_score=hw.get("global_inference_score", None),
                global_inference_label=hw.get("global_inference_label", None),
                global_finetuning_score=hw.get("global_finetuning_score", None),
                global_finetuning_label=hw.get("global_finetuning_label", None),
                cpu_score=hw.get("cpu_score", None),
                gpu_score=hw.get("gpu_score", None),
            )
            db.add(persist_hw_infos)
            db.commit()
            logging.info("Hardware info persisted to database.")
        else:
            logging.info("Hardware info already exists in database, skipping creation.")

    except Exception as e:
        logging.error(f"Error during startup event: {e}")
        db.rollback()
        raise
    finally:
        db.close()

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