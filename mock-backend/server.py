#!/usr/bin/env python3
"""
Standalone Mock Backend for Erudi
A FastAPI-based mock server that provides all the endpoints needed by the Erudi frontend.
"""

import asyncio
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import sys
import signal
import os

# Data Models
class LLM(BaseModel):
    id: int
    name: str
    local: int
    link: str
    type: str
    description: str
    model_metadata: str

class ConversationCreate(BaseModel):
    llm_id: int
    temperature: float = 0.2
    top_p: float = 0.5
    max_tokens: int = 1024
    custom_prompt: str = ""

class ConversationUpdate(BaseModel):
    name: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    custom_prompt: Optional[str] = None

class QueryRequest(BaseModel):
    question: str
    language: str = "en"
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_new_tokens: Optional[int] = None

class GenerateTitleRequest(BaseModel):
    question: str

class ErrorMessageRequest(BaseModel):
    error_message: str

class BulkDeleteRequest(BaseModel):
    conversation_ids: List[int]

class StarMessageRequest(BaseModel):
    message_id: int

class ArenaQueryRequest(BaseModel):
    question: str

# Initialize FastAPI app
app = FastAPI(title="Erudi Mock Backend", description="Mock backend for Erudi development")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory data store
conversation_id_counter = 1
message_id_counter = 1
llm_id_counter = 4

mock_conversations = []
mock_messages = []

# Mock LLMs
mock_llms = [
    LLM(
        id=1,
        name="Mistral 7B Instruct v0.3",
        local=1,
        link="mistralai/Mistral-7B-Instruct-v0.3",
        type="mistral",
        description="A powerful 7B parameter instruction-following model optimized for conversation",
        model_metadata=json.dumps({
            "parameters": "7B",
            "quantization": "None",
            "precision": "float16"
        })
    ),
    LLM(
        id=2,
        name="Gemma 2B IT",
        local=0,
        link="google/gemma-2b-it",
        type="gemma",
        description="Google's lightweight conversational AI model",
        model_metadata=json.dumps({
            "parameters": "2B",
            "quantization": "None",
            "precision": "float16"
        })
    ),
    LLM(
        id=3,
        name="CodeLlama 7B",
        local=1,
        link="codellama/CodeLlama-7b-hf",
        type="codellama",
        description="Code generation and understanding model",
        model_metadata=json.dumps({
            "parameters": "7B",
            "quantization": "4bit",
            "precision": "int4"
        })
    )
]

# Mock hardware info
mock_hardware_info = {
    "chip_model": "Apple M1 Pro",
    "cpu_model": "Apple M1 Pro 10-Core CPU",
    "gpu_model": "Apple M1 Pro 16-Core GPU",
    "total_ram_gb": 16.0,
    "available_ram_gb": 12.8,
    "gpu_vram_total_gb": None,
    "disk_total_gb": 512.0,
    "disk_available_gb": 128.5,
    "gpu_cores": 16,
    "estimated_gpu_tflops": 5.2,
    "memory_bandwidth_gbs": 200.0,
    "neural_engine_tops": 15.8,
    "architecture": "5nm",
    "is_apple_silicon": True,
    "mps_available": True,
    "unified_memory": True,
    "global_finetuning_score": 85.0,
    "global_finetuning_label": "Excellent",
    "cpu_eval_score": 92.0,
    "gpu_eval_score": 88.0,
    "memory_score": 85.0
}

mock_app_startup_info = {
    "global_finetuning_score": 85.0,
    "global_finetuning_label": "Excellent"
}

# Utility functions
def validate_conversation_id(id: int) -> bool:
    return id > 0

def validate_llm_id(id: int) -> bool:
    return any(llm.id == id for llm in mock_llms)

def format_datetime() -> str:
    return datetime.now().isoformat()

def find_conversation(id: int):
    return next((conv for conv in mock_conversations if conv["id"] == id), None)

def find_llm(id: int):
    return next((llm for llm in mock_llms if llm.id == id), None)

# Health check endpoint
@app.get("/health")
async def health_check_simple():
    return {"status": "ok", "message": "Python mock backend is running", "timestamp": format_datetime()}

@app.get("/main_window/health")
async def health_check():
    return {"status": "ok", "message": "Python mock backend is running", "timestamp": format_datetime()}

# Welcome popup
@app.get("/main_window/welcome-popup")
async def welcome_popup():
    return {"show_popup": False}

# Hardware endpoints
@app.get("/hardware/app_startup")
async def hardware_app_startup():
    return mock_app_startup_info

@app.get("/hardware/training")
async def hardware_training():
    return mock_hardware_info

@app.get("/hardware/detailed")
async def hardware_detailed():
    return mock_hardware_info

# LLM endpoints
@app.get("/main_window/llms")
async def get_llms():
    return [llm.dict() for llm in mock_llms]

@app.get("/main_window/llms/local")
async def get_local_llms():
    return [llm.dict() for llm in mock_llms if llm.local == 1]

@app.get("/main_window/llms/remote")
async def get_remote_llms():
    return [llm.dict() for llm in mock_llms if llm.local == 0]

@app.get("/main_window/llms/{llm_id}")
async def get_llm(llm_id: int):
    llm = find_llm(llm_id)
    if not llm:
        raise HTTPException(status_code=404, detail="LLM not found")
    return llm.dict()

@app.post("/main_window/llms")
async def create_llm(llm_data: dict):
    global llm_id_counter
    
    required_fields = ["name", "local", "link"]
    for field in required_fields:
        if field not in llm_data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
    
    new_llm = LLM(
        id=llm_id_counter,
        name=llm_data["name"],
        local=llm_data["local"],
        link=llm_data["link"],
        type=llm_data.get("type", "unknown"),
        description=llm_data.get("description", ""),
        model_metadata=json.dumps({
            "parameters": "Unknown",
            "quantization": "None",
            "precision": "float16"
        })
    )
    llm_id_counter += 1
    mock_llms.append(new_llm)
    return new_llm.dict()

@app.put("/main_window/llms/{llm_id}")
async def update_llm(llm_id: int, llm_data: dict):
    llm = find_llm(llm_id)
    if not llm:
        raise HTTPException(status_code=404, detail="LLM not found")
    
    # Update the LLM in place
    for idx, l in enumerate(mock_llms):
        if l.id == llm_id:
            for key, value in llm_data.items():
                if hasattr(l, key):
                    setattr(l, key, value)
            return l.dict()

@app.delete("/main_window/llms/{llm_id}")
async def delete_llm(llm_id: int):
    global mock_llms
    original_length = len(mock_llms)
    mock_llms = [llm for llm in mock_llms if llm.id != llm_id]
    
    if len(mock_llms) == original_length:
        raise HTTPException(status_code=404, detail="LLM not found")
    
    return {"message": "Model deleted successfully"}

# Conversation endpoints
@app.get("/conversations")
async def get_conversations():
    return mock_conversations

@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: int):
    if not validate_conversation_id(conversation_id):
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
    
    conversation = find_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    messages = [msg for msg in mock_messages if msg["conversation_id"] == conversation_id]
    return {**conversation, "messages": messages}

@app.post("/conversations")
async def create_conversation(conv_data: ConversationCreate):
    global conversation_id_counter
    
    if not validate_llm_id(conv_data.llm_id):
        raise HTTPException(status_code=400, detail="Invalid LLM ID")
    
    now = format_datetime()
    new_conversation = {
        "id": conversation_id_counter,
        "llm_id": conv_data.llm_id,
        "name": "New Conversation",
        "created_at": now,
        "last_message_time": now,
        "temperature": conv_data.temperature,
        "top_p": conv_data.top_p,
        "max_tokens": conv_data.max_tokens,
        "custom_prompt": conv_data.custom_prompt
    }
    
    conversation_id_counter += 1
    mock_conversations.append(new_conversation)
    return new_conversation

@app.patch("/conversations/{conversation_id}")
async def update_conversation(conversation_id: int, conv_data: ConversationUpdate):
    if not validate_conversation_id(conversation_id):
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
    
    conversation = find_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Update fields
    update_data = conv_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            conversation[key] = value
    
    conversation["last_message_time"] = format_datetime()
    return conversation

@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int):
    global mock_conversations, mock_messages
    
    # Remove conversation
    original_length = len(mock_conversations)
    mock_conversations = [conv for conv in mock_conversations if conv["id"] != conversation_id]
    
    if len(mock_conversations) == original_length:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Remove messages
    mock_messages = [msg for msg in mock_messages if msg["conversation_id"] != conversation_id]
    
    return {"message": "Conversation deleted successfully"}

@app.get("/conversations/{conversation_id}/fetch_messages")
async def fetch_messages(conversation_id: int):
    if not validate_conversation_id(conversation_id):
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
    
    messages = [msg for msg in mock_messages if msg["conversation_id"] == conversation_id]
    return messages

@app.post("/conversations/{conversation_id}/query")
async def query_conversation(conversation_id: int, query_data: QueryRequest):
    global message_id_counter
    
    if not validate_conversation_id(conversation_id):
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
    
    if not query_data.question or not query_data.question.strip():
        raise HTTPException(status_code=400, detail="Question is required and must be non-empty")
    
    conversation = find_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Add user message
    user_message = {
        "id": message_id_counter,
        "conversation_id": conversation_id,
        "sender": "user",
        "content": query_data.question.strip(),
        "timestamp": format_datetime(),
        "starred": False
    }
    message_id_counter += 1
    mock_messages.append(user_message)
    
    # Update conversation timestamp
    conversation["last_message_time"] = format_datetime()
    
    # Stream response
    async def generate_response():
        responses = [
            "Thank you for your question! This is a comprehensive mock response from the Python Erudi backend. ",
            "I'm simulating realistic streaming behavior that mimics how a real language model would respond. ",
            "The Python mock backend includes proper error handling, data validation, and follows the actual API schema. ",
            "This response demonstrates conversation memory, context awareness, and realistic timing between chunks. ",
            "You can test all the UI features including the typing indicator, message history, and conversation management. ",
            "The backend properly handles edge cases like invalid IDs, missing parameters, and malformed requests."
        ]
        
        full_response = ""
        for chunk in responses:
            yield chunk
            full_response += chunk
            await asyncio.sleep(0.8)  # Simulate realistic timing
        
        # Add assistant message after streaming is complete
        assistant_message = {
            "id": message_id_counter,
            "conversation_id": conversation_id,
            "sender": "assistant",
            "content": full_response,
            "timestamp": format_datetime(),
            "starred": False
        }
        mock_messages.append(assistant_message)
    
    return StreamingResponse(generate_response(), media_type="text/plain")

@app.post("/conversations/{conversation_id}/generate_title")
async def generate_title(conversation_id: int, title_data: GenerateTitleRequest):
    if not validate_conversation_id(conversation_id):
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
    
    conversation = find_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Generate title based on question keywords
    def generate_title_text(text: str) -> str:
        keywords = [word for word in text.lower().split() 
                   if len(word) > 3 and word not in ['what', 'how', 'why', 'when', 'where', 'can', 'could', 'would', 'should']]
        
        if not keywords:
            return "General Discussion"
        
        return ' '.join(word.capitalize() for word in keywords[:3])
    
    title = generate_title_text(title_data.question) if title_data.question else "General Discussion"
    
    # Stream the title generation
    async def generate_title_stream():
        for char in title:
            yield char
            await asyncio.sleep(0.1)
        
        # Update conversation title
        conversation["name"] = title
    
    return StreamingResponse(generate_title_stream(), media_type="text/plain")

@app.post("/conversations/{conversation_id}/store_error_message")
async def store_error_message(conversation_id: int, error_data: ErrorMessageRequest):
    global message_id_counter
    
    if not validate_conversation_id(conversation_id):
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
    
    # Store error as a message
    if error_data.error_message:
        error_message = {
            "id": message_id_counter,
            "conversation_id": conversation_id,
            "sender": "system",
            "content": f"Error: {error_data.error_message}",
            "timestamp": format_datetime(),
            "starred": False
        }
        message_id_counter += 1
        mock_messages.append(error_message)
    
    return {"success": True}

@app.delete("/conversations/delete_bulk")
async def delete_bulk_conversations(delete_data: BulkDeleteRequest):
    global mock_conversations, mock_messages
    
    deleted_count = 0
    for conv_id in delete_data.conversation_ids:
        # Remove conversation
        original_length = len(mock_conversations)
        mock_conversations = [conv for conv in mock_conversations if conv["id"] != conv_id]
        
        if len(mock_conversations) < original_length:
            deleted_count += 1
            # Remove messages for this conversation
            mock_messages = [msg for msg in mock_messages if msg["conversation_id"] != conv_id]
    
    return {"success": True, "deleted_count": deleted_count}

# Message endpoints
@app.delete("/messages/{message_id}")
async def delete_message(message_id: int):
    global mock_messages
    
    original_length = len(mock_messages)
    mock_messages = [msg for msg in mock_messages if msg["id"] != message_id]
    
    if len(mock_messages) == original_length:
        raise HTTPException(status_code=404, detail="Message not found")
    
    return {"message": "Message deleted successfully"}

@app.post("/conversations/star_message")
async def star_message(star_data: StarMessageRequest):
    message = next((msg for msg in mock_messages if msg["id"] == star_data.message_id), None)
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    message["starred"] = True
    return {"success": True}

@app.post("/conversations/unstar_message")
async def unstar_message(unstar_data: StarMessageRequest):
    message = next((msg for msg in mock_messages if msg["id"] == unstar_data.message_id), None)
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    message["starred"] = False
    return {"success": True}

# Arena endpoints
@app.post("/arena/{llm_id}/query")
async def arena_query(llm_id: int, query_data: ArenaQueryRequest):
    if not validate_llm_id(llm_id):
        raise HTTPException(status_code=400, detail="Invalid LLM ID")
    
    if not query_data.question:
        raise HTTPException(status_code=400, detail="Question is required")
    
    llm = find_llm(llm_id)
    
    async def generate_arena_response():
        response_text = f"This is a mock arena response from {llm.name}. I'm designed to help you compare different models side by side. Each model has its own strengths and characteristics that you can evaluate through direct comparison."
        
        words = response_text.split(' ')
        for word in words:
            yield word + ' '
            await asyncio.sleep(0.3)
    
    return StreamingResponse(generate_arena_response(), media_type="text/plain")

# Training endpoints
@app.get("/training/{training_id}/status")
async def training_status(training_id: int):
    import random
    statuses = ['pending', 'running', 'completed', 'failed']
    status = random.choice(statuses)
    
    return {
        "status": status,
        "progress": 100 if status == 'completed' else random.randint(0, 99),
        "eta": random.randint(0, 3600) if status == 'running' else None,
        "current_epoch": random.randint(1, 10) if status == 'running' else None,
        "total_epochs": 10,
        "loss": round(random.random() * 2, 4) if status == 'running' else None
    }

@app.post("/train")
async def start_training(training_data: dict):
    if "llm_id" not in training_data or "dataset_path" not in training_data:
        raise HTTPException(status_code=400, detail="LLM ID and dataset path are required")
    
    return {
        "training_id": int(time.time()),
        "status": "started",
        "message": "Training job initiated successfully"
    }

# Knowledge base endpoints (simplified)
@app.api_route("/knowledge_base/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def knowledge_base_fallback(path: str):
    return {
        "success": True,
        "data": [],
        "message": "Knowledge base feature is not implemented in the mock backend"
    }

# Basic routes
@app.get("/main_window/local-models")
async def get_local_models():
    return [llm.dict() for llm in mock_llms if llm.local == 1]

@app.get("/main_window/available-models")
async def get_available_models():
    return [llm.dict() for llm in mock_llms if llm.local == 0]

@app.get("/main_window/train-new-model")
async def train_new_model():
    return {"available": True, "supported_formats": ["jsonl", "csv", "txt"]}

# Graceful shutdown handling
def signal_handler(signum, frame):
    print(f"\nReceived signal {signum}, shutting down gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    print(f"Starting Python Mock Backend on port {port}")
    print(f"Process ID: {os.getpid()}")
    print("Press Ctrl+C to stop the server")
    
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info",
        access_log=False
    )