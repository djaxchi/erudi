from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models.StartupVariables import StartupVariables
from app.database import get_db

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

@router.get("/main_window/welcome-popup")
async def get_welcome_popup_status(
    db: Session = Depends(get_db)
):
    try:
        vars = db.query(StartupVariables).first()
        if vars:
            welcome_popup_bool = vars.welcome_popup_has_already_displayed
            if welcome_popup_bool == True:
                return {"has_already_displayed": True}
            vars.welcome_popup_has_already_displayed = True
            db.commit()
            return {"has_already_displayed": False}
        else:
            vars = StartupVariables(
                welcome_popup_has_already_displayed=False
            )
            db.add(vars)
            db.commit()
            return {"has_already_displayed": False}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=f"Failed to give welcome popup status: {str(e)}")