from fastapi import APIRouter, Depends, HTTPException
from app.entities.StartupVariables import StartupVariables
from app.database import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/main_window", tags=["main_window"])

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
                welcome_popup_has_already_displayed=True
            )
            db.add(vars)
            db.commit()
            return {"has_already_displayed": False}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=f"Failed to give welcome popup status: {str(e)}")