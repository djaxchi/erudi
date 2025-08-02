from fastapi import APIRouter

router = APIRouter()

@router.get("/main_window/local-models")
async def get_local_models():
    return {"message": "This is the Local Models endpoint."}

@router.get("/main_window/available-models")
async def get_available_models():
    return {"message": "This is the Available Models endpoint."}

@router.get("/main_window/train-new-model")
async def train_new_model():
    return {"message": "This is the Train New Model endpoint."}

@router.get("/main_window/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "message": "Backend is running"}