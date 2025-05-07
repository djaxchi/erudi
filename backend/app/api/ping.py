from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
def pong():
    return {"message": "pong from backend"}