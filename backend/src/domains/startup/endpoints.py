from fastapi import Depends, HTTPException
from src.core.api import startup_router as router

from src.database import get_db
from sqlalchemy.orm import Session

from src.entities.StartupVariables import StartupVariables

@router.get("/welcome-popup")
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