from src.core.api import health_router as router

@router.get("")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "message": "Backend is running"}