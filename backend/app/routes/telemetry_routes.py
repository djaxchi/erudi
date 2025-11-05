"""
Telemetry API Routes
Handles beta consent and event tracking
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import uuid
import logging

from app.database import get_db
from app.models.StartupVariables import StartupVariables
from app.utils.telemetry import get_telemetry

logger = logging.getLogger(__name__)

router = APIRouter()


class ConsentRequest(BaseModel):
    accepted: bool


class ConsentResponse(BaseModel):
    beta_consent_accepted: bool
    user_id: str


class TelemetryEventRequest(BaseModel):
    event_type: str
    properties: Optional[Dict[str, Any]] = None


class TelemetryStatusResponse(BaseModel):
    enabled: bool
    queue_size: int
    sheets_configured: bool


@router.get("/telemetry/consent", response_model=ConsentResponse)
def get_consent_status(db: Session = Depends(get_db)):
    """
    Check if user has accepted beta consent
    Returns consent status and user ID
    """
    try:
        startup_vars = db.query(StartupVariables).first()
        
        if not startup_vars:
            # Create new record
            startup_vars = StartupVariables(
                beta_consent_accepted=False,
                user_id=str(uuid.uuid4())
            )
            db.add(startup_vars)
            db.commit()
            db.refresh(startup_vars)
        
        # Ensure user_id exists
        if not startup_vars.user_id:
            startup_vars.user_id = str(uuid.uuid4())
            db.commit()
            db.refresh(startup_vars)
        
        return ConsentResponse(
            beta_consent_accepted=startup_vars.beta_consent_accepted or False,
            user_id=startup_vars.user_id
        )
        
    except Exception as e:
        logger.error(f"Error getting consent status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/telemetry/consent", response_model=ConsentResponse)
def set_consent(
    consent: ConsentRequest,
    db: Session = Depends(get_db)
):
    """
    Set beta consent acceptance
    """
    try:
        startup_vars = db.query(StartupVariables).first()
        
        if not startup_vars:
            startup_vars = StartupVariables(
                beta_consent_accepted=consent.accepted,
                beta_consent_timestamp=datetime.utcnow() if consent.accepted else None,
                user_id=str(uuid.uuid4())
            )
            db.add(startup_vars)
        else:
            startup_vars.beta_consent_accepted = consent.accepted
            startup_vars.beta_consent_timestamp = datetime.utcnow() if consent.accepted else None
            
            # Ensure user_id exists
            if not startup_vars.user_id:
                startup_vars.user_id = str(uuid.uuid4())
        
        db.commit()
        db.refresh(startup_vars)
        
        # Track consent event
        telemetry = get_telemetry()
        if telemetry and consent.accepted:
            telemetry.track_event(
                "beta_consent_accepted",
                user_id=startup_vars.user_id,
                properties={
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        return ConsentResponse(
            beta_consent_accepted=startup_vars.beta_consent_accepted,
            user_id=startup_vars.user_id
        )
        
    except Exception as e:
        logger.error(f"Error setting consent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/telemetry/event")
def track_event(
    event: TelemetryEventRequest,
    db: Session = Depends(get_db)
):
    """
    Track a telemetry event
    Only works if user has consented
    """
    try:
        # Check consent
        startup_vars = db.query(StartupVariables).first()
        
        if not startup_vars or not startup_vars.beta_consent_accepted:
            # Silently ignore if no consent
            return {"status": "ignored", "reason": "no_consent"}
        
        # Track event
        telemetry = get_telemetry()
        if telemetry:
            telemetry.track_event(
                event.event_type,
                user_id=startup_vars.user_id,
                properties=event.properties
            )
            return {"status": "tracked"}
        else:
            return {"status": "telemetry_disabled"}
            
    except Exception as e:
        logger.error(f"Error tracking event: {e}")
        # Don't fail the request if telemetry fails
        return {"status": "error", "error": str(e)}


@router.get("/telemetry/status", response_model=TelemetryStatusResponse)
def get_telemetry_status(db: Session = Depends(get_db)):
    """
    Get telemetry system status
    """
    try:
        telemetry = get_telemetry()
        
        if telemetry:
            return TelemetryStatusResponse(
                enabled=True,
                queue_size=telemetry.get_queue_size(),
                sheets_configured=telemetry.sheets_enabled
            )
        else:
            return TelemetryStatusResponse(
                enabled=False,
                queue_size=0,
                sheets_configured=False
            )
            
    except Exception as e:
        logger.error(f"Error getting telemetry status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
