from datetime import datetime
import os
import shutil
from contextlib import asynccontextmanager

from .utils.inference_utils import ModelManager
from .utils.hardware_info import get_hardware_eval_for_apple_silicon

from .models.StaticHardwareInfos import StaticHardwareInfo
from .routes import knowledgeBase_routes
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
from .models.KnowledgeBase import KnowledgeBase
from .models.VectorStore import VectorStore
from .models.KBJob import KBJobModel
from .models.StaticHardwareInfos import StaticHardwareInfo
from .models.StartupVariables import StartupVariables

from huggingface_hub import HfApi
from dotenv import load_dotenv

load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")
api = HfApi(token=HF_TOKEN)

# Global size map for model size estimates
SIZE_MAP = {
    # Mistral models (full precision)
    "mistralai/Mistral-7B-Instruct-v0.3": "~13.5 GB",
    "mistralai/Mistral-7B-v0.3": "~13.5 GB",
    # Gemma models (full precision)
    "google/gemma-3-1b-it": "~2.5 GB",
    "google/gemma-2-2b-it": "~5.5 GB", 
    "google/gemma-3-4b-it": "~9.0 GB",
}

# Mapping of original model links to MLX-quantized versions (same as in llm_downloader.py)
MLX_MODEL_MAPPING = {
    "mistralai/Mistral-7B-Instruct-v0.3": "mlx-community/Mistral-7B-Instruct-v0.3-4bit",
    "mistralai/Mistral-7B-v0.3": "mlx-community/Mistral-7B-v0.3-4bit",
    "google/gemma-2-2b-it": "mlx-community/gemma-2-2b-it-4bit",
    "google/gemma-3-4b-it": "mlx-community/gemma-3-4b-it-4bit",
    "mistralai/Ministral-8B-Instruct-2410": "mlx-community/Ministral-8B-Instruct-2410-4bit",
    "google/gemma-3-12b-it": "mlx-community/gemma-3-12b-it-4bit",
}

def get_mlx_model_size(mlx_link):
    """Get the actual size of MLX quantized model from Hugging Face"""
    try:
        repo_info = api.repo_info(mlx_link, files_metadata=True)
        total_size = sum(file.size for file in repo_info.siblings if file.size)
        # Convert to GB
        size_gb = total_size / (1024**3)
        return f"~{size_gb:.1f} GB"
    except Exception as e:
        logging.error(f"Error getting MLX model size for {mlx_link}: {e}")
        # Fallback estimates based on quantization
        if "4bit" in mlx_link.lower():
            return "~3-4 GB"  # Rough estimate for 4-bit 7B models
        elif "8bit" in mlx_link.lower():
            if "1b" in mlx_link.lower():
                return "~1-2 GB"
            elif "2b" in mlx_link.lower():
                return "~2-3 GB"
            elif "4b" in mlx_link.lower():
                return "~4-5 GB"
        return "Unknown"

def get_model_size_estimate(model_name, link):
    """Get approximate model size for known base models and their derivatives"""
    # First check for exact match
    if link in SIZE_MAP:
        return SIZE_MAP[link]
    
    # Check for derived models based on model name patterns
    model_name_lower = model_name.lower()
    link_lower = link.lower()
    
    # Mistral 7B derivatives
    if ("mistral" in model_name_lower and ("7b" in model_name_lower or "7b" in link_lower)):
        return "~13.5 GB"
    
    # Gemma derivatives based on parameter count
    if "gemma" in model_name_lower or "gemma" in link_lower:
        if "1b" in model_name_lower or "1b" in link_lower:
            return "~2.5 GB"
        elif "2b" in model_name_lower or "2b" in link_lower:
            return "~5.5 GB"
        elif "4b" in model_name_lower or "4b" in link_lower:
            return "~9.0 GB"
        elif "7b" in model_name_lower or "7b" in link_lower:
            return "~13.5 GB"
    
    return "Unknown"

def get_parameter_count_from_name(model_name, link):
    """Extract parameter count from model name or link"""
    import re
    
    # Combine name and link for searching
    search_text = f"{model_name} {link}".lower()
    
    # Look for common parameter patterns
    # Match patterns like: 7b, 7B, 70b, 13b, 1.5b, etc.
    param_patterns = [
        r'(\d+\.?\d*)b(?:illion)?',  # 7b, 7.5b, 70b
        r'(\d+\.?\d*)m(?:illion)?',  # 350m, 125m
    ]
    
    for pattern in param_patterns:
        matches = re.findall(pattern, search_text)
        if matches:
            param_value = float(matches[0])
            if 'b' in pattern:
                return f"{param_value}B"
            else:  # million
                return f"{int(param_value)}M"
    
    return "Unknown"

def format_model_info_metadata(model_info, size_estimate=None, quantized=False):
    """Format ModelInfo object into a structured string for storage"""
    try:
        # Extract parameter count from model name
        param_count = get_parameter_count_from_name(model_info.id, model_info.id)
        
        metadata_str = f"""Model ID: {model_info.id}
                            Author: {model_info.author}
                            Created: {model_info.created_at}
                            Downloads: {model_info.downloads} 
                            Likes: {model_info.likes}
                            Library: {model_info.library_name}
                            Pipeline: {model_info.pipeline_tag}
                            Size: {size_estimate or 'Unknown'}
                            Parameters: {param_count}
                            Quantized: {quantized}
                            Private: {model_info.private}
                            Gated: {model_info.gated}
                            Tags: {', '.join(model_info.tags[:10]) if model_info.tags else 'None'}{'...' if model_info.tags and len(model_info.tags) > 10 else ''}
                            SHA: {model_info.sha}
                            Last Modified: {model_info.last_modified}"""
        return metadata_str
    except Exception as e:
        return f"Error formatting metadata: {str(e)}"

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
        db.query(KBJobModel).delete()
        db.query(StartupVariables).delete()

        db.commit()
        logging.info("All data deleted successfully.")
    except Exception as e:
        logging.error(f"Error deleting data: {e}")
        db.rollback()
    finally:
        db.close()

async def startup_populate_database():
    
    db: Session = SessionLocal()


    try:

        # Populate the database with some base models with metadata
        base_models = [
            ("Mistral-7B-Instruct-v0.3", "mistralai/Mistral-7B-Instruct-v0.3", "mistral"),
            ("Mistral-7B-v0.3", "mistralai/Mistral-7B-v0.3", "mistral"),
            ("Gemma-3-1B-it", "google/gemma-3-1b-it", "gemma"),
            ("Gemma-2-2B-it", "google/gemma-2-2b-it", "gemma"),
            ("Gemma-3-4B-it", "google/gemma-3-4b-it", "gemma"),
            ("Ministral-8B-Instruct", "mistralai/Ministral-8B-Instruct-2410", "mistral"),
            ("gemma-3-12b-it", "google/gemma-3-12b-it", "gemma")
        ]
        
        for name, link, model_type in base_models:
            existing_model = db.query(Llm).filter(Llm.name == name).first()
            
            param_str = get_parameter_count_from_name(name, link)
            if "B" in param_str:
                param_size = float(param_str.replace("B", ""))
            elif "M" in param_str:
                param_size = float(param_str.replace("M", "")) // 1000
            else:
                param_size = -1.0  # Unknown

            if not existing_model:
                try:
                    # Check if MLX quantized version exists
                    mlx_link = MLX_MODEL_MAPPING.get(link)
                    is_quantized = mlx_link is not None
                    
                    # Fetch metadata from ORIGINAL model (for author, likes, downloads)
                    model_info = api.model_info(link)
                    
                    # Get size from MLX version if available, otherwise from original
                    if is_quantized:
                        size_estimate = get_mlx_model_size(mlx_link)
                        # Store the MLX link as the actual link to download
                        actual_link = mlx_link
                    else:
                        size_estimate = get_model_size_estimate(name, link)
                        actual_link = link
                
                    base_model = Llm(
                        name=name,
                        local=0,
                        link=actual_link,  # Use MLX link if available
                        type=model_type,
                        quantized=1 if is_quantized else 0,
                        model_metadata=format_model_info_metadata(model_info, size_estimate, is_quantized),
                        param_size=param_size
                    )
                    db.add(base_model)
                    print(f"Added base model {name} (quantized={is_quantized}) with metadata and size: {size_estimate}")
                except Exception as e:
                    print(f"Error fetching metadata for {name}: {e}")
                    # Fallback: create with just size estimate
                    mlx_link = MLX_MODEL_MAPPING.get(link)
                    is_quantized = mlx_link is not None
                    
                    if is_quantized:
                        size_estimate = get_mlx_model_size(mlx_link)
                        actual_link = mlx_link
                    else:
                        size_estimate = get_model_size_estimate(name, link)
                        actual_link = link
                    
                    fallback_metadata = f"Size: {size_estimate}\nModel ID: {link}\nQuantized: {is_quantized}\nAuthor: Unknown\nLibrary: Unknown"
                    base_model = Llm(
                        name=name,
                        local=0,
                        link=actual_link,
                        type=model_type,
                        quantized=1 if is_quantized else 0,
                        model_metadata=fallback_metadata,
                        param_size=param_size
                    )
                    db.add(base_model)
                    print(f"Added base model {name} (quantized={is_quantized}) with size estimate: {size_estimate}")

        LIMIT_MODELS = 100  # Limit the number of models to fetch and add
        
        SKIP_IDS = [
            "mistral-7b-instruct-v0.3",
            "mistral-7b-v0.3",
            "gemma-3-1b-it",
            "gemma-2-2b-it",
            "gemma-3-4b-it"
        ]
        SKIP_TERMS = [
            "gguf","gptq","bnb","4bit","8bit","f16","awq",
            "q4","q5","q6", "q8", "fp8","fp16","fp4","sqft", 'quantized',
            "quant", "quantized", "quantization", "lora", "knut",
            "sft", "int4", "int8", "int16", "int32", "int64",
            "peft", "test"
        ]
        # Populate with some Mistral-7B variant community models
        for i,m in enumerate(api.list_models(search="Mistral-7B v0.3", sort="downloads", direction=-1)):
            if i >= LIMIT_MODELS:
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

            # Get size estimate for community model
            size_estimate = get_model_size_estimate(m.modelId.split("/")[-1], m.modelId)
            
            # Extract parameter count from model name
            param_str = get_parameter_count_from_name(m.modelId.split("/")[-1], m.modelId)
            if "B" in param_str:
                param_size = float(param_str.replace("B", ""))
            elif "M" in param_str:
                param_size = float(param_str.replace("M", "")) / 1000
            else:
                param_size = 4.0  # Default fallback

            llm_entry = Llm(
                name=m.modelId.split("/")[-1],  
                local=0,
                link=m.modelId,
                type="mistral" if "mistral" in m.modelId.lower() else "gemma",
                quantized=0,  # Community models are not pre-quantized
                model_metadata=format_model_info_metadata(m, size_estimate, quantized=False),
                param_size=param_size
            )
            db.add(llm_entry)

        for i, m in enumerate(api.list_models(search="Gemma 1B", sort="downloads", direction=-1)):
            if i >= LIMIT_MODELS:
                break
            mid = m.modelId.lower()
            mname = mid.split("/")[-1].lower()
            # skip exact matches or any unwanted substring
            if mname in SKIP_IDS or any(term in mid for term in SKIP_TERMS):
                continue

            exists = db.query(Llm).filter_by(link=m.modelId).first()
            if exists:
                continue

            # Get size estimate for community model
            size_estimate = get_model_size_estimate(m.modelId.split("/")[-1], m.modelId)
            
            # Extract parameter count from model name
            param_str = get_parameter_count_from_name(m.modelId.split("/")[-1], m.modelId)
            if "B" in param_str:
                param_size = float(param_str.replace("B", ""))
            elif "M" in param_str:
                param_size = float(param_str.replace("M", "")) / 1000
            else:
                param_size = 1.0  # Default fallback for Gemma (usually smaller)

            llm_entry = Llm(
                name=m.modelId.split("/")[-1],  
                local=0,
                link=m.modelId,
                type="mistral" if "mistral" in m.modelId.lower() else "gemma",
                quantized=0,  # Community models are not pre-quantized
                model_metadata=format_model_info_metadata(m, size_estimate, quantized=False),
                param_size=param_size
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
                if os.path.exists(llm.link):
                    shutil.rmtree(llm.link, ignore_errors=True)
                db.delete(llm)
            if job.temp_local_model_link and job.temp_local_model_link != "":
                if os.path.exists(job.temp_local_model_link):
                    shutil.rmtree(job.temp_local_model_link, ignore_errors=True)
                if "temp" not in job.temp_local_model_link and os.path.exists("./data/models/temp_"+str(job.local_model_id)):
                    shutil.rmtree("./data/models/temp_"+str(job.local_model_id), ignore_errors=True)
                job.temp_local_model_link = ""
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
                if os.path.exists(llm.link):
                    shutil.rmtree(llm.link, ignore_errors=True)
                db.delete(llm)
            job.llm_id = -1
            job.updated_at = datetime.now()
            
            db.commit()
            logging.warning(f"Marked unfinished TrainingJob {job.id} as failed.")
        db.commit()

        # Check the unfinished KBJobs
        unfinished_kb_jobs = db.query(KBJobModel).filter(
            KBJobModel.status.in_(["running", "pending"])
        ).all()
        for job in unfinished_kb_jobs:
            job.status = "failed"
            job.error_message = "Knowledge Base creation was not completed due to application shutdown."
            new_llm = db.query(Llm).filter(Llm.id == job.new_model_id).first()
            if new_llm:
                db.delete(new_llm)
            vector_store = db.query(VectorStore).filter(VectorStore.kb_id == job.kb_id).first()
            if vector_store:
                db.delete(vector_store)
            kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == job.kb_id).first()
            if kb:
                if kb.index_path:
                    if os.path.exists(kb.index_path):
                        shutil.rmtree(kb.index_path, ignore_errors=True)
                db.delete(kb)
            job.new_model_id = -1
            job.updated_at = datetime.now()
            
            db.commit()
            logging.warning(f"Marked unfinished KBJob {job.id} as failed.")
        db.commit()

        persist_hw_infos = db.query(StaticHardwareInfo).first()
        if not persist_hw_infos:
            try:
                # Get Apple Silicon hardware evaluation
                logging.info("Evaluating Apple Silicon hardware...")
                hw = get_hardware_eval_for_apple_silicon()
                logging.info("Hardware evaluation completed successfully.")
            except Exception as e:
                logging.warning(f"Hardware evaluation failed: {e}. Using fallback values.")
                hw = {
                    "chip_model": "Unknown",
                    "cpu_model": "Unknown CPU",
                    "gpu_name": "Unknown GPU",
                    "total_memory_gb": 8.0,
                    "available_memory_gb": 4.0,
                    "disk_total_gb": 100.0,
                    "disk_available_gb": 50.0,
                    "global_inference_score": 20.0,
                    "global_inference_label": "Poor",
                    "global_finetuning_score": 15.0,
                    "global_finetuning_label": "Very Poor",
                    "cpu_score": 30.0,
                    "gpu_score": 20.0,
                    "memory_score": 25.0,
                    "mps_available": False,
                    "is_apple_silicon": False
                }
            
            persist_hw_infos = StaticHardwareInfo(
                # Basic hardware identification
                chip_model=hw.get("chip_model"),
                cpu_model=hw.get("cpu_model"),
                gpu_name=hw.get("gpu_name"),
                
                # Memory information (unified memory for Apple Silicon)
                system_ram_gb=hw.get("total_memory_gb"),
                available_ram_gb=hw.get("available_memory_gb"),
                
                # Storage information
                disk_total_gb=hw.get("disk_total_gb"),
                disk_avail_gb=hw.get("disk_available_gb"),
                
                # Apple Silicon specific GPU specs
                gpu_cores=hw.get("gpu_cores"),
                estimated_gpu_tflops=hw.get("estimated_gpu_tflops"),
                
                # Apple Silicon specific performance metrics
                memory_bandwidth_gbs=hw.get("memory_bandwidth_gbs"),
                neural_engine_tops=hw.get("neural_engine_tops"),
                cpu_performance_units=hw.get("cpu_performance_units"),
                
                # Architecture details
                architecture=hw.get("architecture"),
                is_apple_silicon=hw.get("is_apple_silicon", False),
                mps_available=hw.get("mps_available", False),
                unified_memory=hw.get("unified_memory", False),
                system_platform=hw.get("system_platform"),
                
                # Performance scores
                global_inference_score=hw.get("global_inference_score"),
                global_inference_label=hw.get("global_inference_label"),
                global_finetuning_score=hw.get("global_finetuning_score"),
                global_finetuning_label=hw.get("global_finetuning_label"),
                cpu_score=hw.get("cpu_score"),
                gpu_score=hw.get("gpu_score"),
                memory_score=hw.get("memory_score"),
                
                # Performance breakdown
                performance_breakdown=hw.get("performance_breakdown")
            )
            db.add(persist_hw_infos)
                
        # Initialize startup variables
        variables = db.query(StartupVariables).first()
        if not variables:
            variables = StartupVariables(
                welcome_popup_has_already_displayed=False
            )
            db.add(variables)
            db.commit()
        else:
            db.refresh(variables)



    except Exception as e:
        logging.error(f"Error during startup event: {e}")
        db.rollback()
        raise
    finally:
        db.close()
        return

# on_startup was deprecated, use lifespan instead
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Before yield comes the startup code
    await createTables()
    #await delete_all_data()
    await startup_populate_database()
    ModelManager.start_cleanup_task()
    yield
    # Shutdown code can go here if needed
    ModelManager.stop_cleanup_task()
    ModelManager.cleanup()

# Initialize FastAPI with the lifespan context manager
app = FastAPI(lifespan=lifespan)

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