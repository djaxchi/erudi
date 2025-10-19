from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])

@router.get("/")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "message": "Backend is running"}