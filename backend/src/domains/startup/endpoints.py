"""FastAPI endpoints for startup state management.

This module provides REST API endpoints for managing application startup state,
including UI flags that persist across app restarts (e.g., welcome popup status).

Architecture:
    - Endpoints use repository pattern via dependency injection.
    - Pydantic schemas validate all request/response data.
    - Structured logging for traceability.
    - Proper error handling with domain-specific exceptions.

Endpoints:
    GET /startup/welcome-popup - Check and update welcome popup display status.

Example:
    curl http://localhost:8000/erudi/startup/welcome-popup
    {"has_already_displayed": false}
"""
from fastapi import Depends, APIRouter
from sqlalchemy.orm import Session

from src.database.core import get_db
from src.domains.startup.repository import Startup_Variables_Repository
from src.domains.startup.schemas import WelcomePopupResponse, ConnectionStatusResponse
from src.core.logging import logger
from src.core.exceptions import DatabaseException
from src.database.seed import is_online

router = APIRouter(prefix="/startup", tags=["startup"])


# ============ Dependency Injection ============

def get_startup_repository(db: Session = Depends(get_db)) -> Startup_Variables_Repository:
    """FastAPI dependency injection factory for Startup_Variables_Repository.

    Args:
        db: SQLAlchemy session (injected by FastAPI via Depends(get_db)).

    Returns:
        Startup_Variables_Repository: Configured repository instance.
    """
    return Startup_Variables_Repository(db)


# ============ Endpoints ============

@router.get("/welcome-popup", response_model=WelcomePopupResponse)
async def get_welcome_popup_status(
    startup_repo: Startup_Variables_Repository = Depends(get_startup_repository),
    db: Session = Depends(get_db),
):
    """Check welcome popup display status and mark as shown if first time.

    Implements "check-and-set" logic: returns False on first call (popup should show),
    then sets flag to True. Subsequent calls return True (popup already shown).

    Args:
        startup_repo: Injected startup variables repository.
        db: Database session for transaction control.

    Returns:
        WelcomePopupResponse: {"has_already_displayed": bool}

    Raises:
        DatabaseException: If database operation fails.

    Example:
        First call:  GET /startup/welcome-popup → {"has_already_displayed": false}
        Second call: GET /startup/welcome-popup → {"has_already_displayed": true}
    """
    try:
        # Get or create singleton startup variables
        vars = startup_repo.get_or_create()
        
        # Check current status
        already_displayed = vars.welcome_popup_has_already_displayed
        
        # If not displayed yet, mark as displayed now
        if not already_displayed:
            startup_repo.mark_welcome_popup_displayed(vars)
            db.commit()
            logger.info("Welcome popup marked as displayed (first time)")
            return WelcomePopupResponse(has_already_displayed=False)
        
        # Already displayed before
        logger.debug("Welcome popup status: already displayed")
        return WelcomePopupResponse(has_already_displayed=True)
        
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to get welcome popup status: {e}")
        raise DatabaseException(
            "Failed to get welcome popup status",
            trace=str(e)
        )


@router.get("/connection-status", response_model=ConnectionStatusResponse)
async def get_connection_status(
    startup_repo: Startup_Variables_Repository = Depends(get_startup_repository),
):
    """Get application connection status and model seeding information.

    Provides real-time information about:
    - Whether app is in offline mode (last seeded from JSON fallback)
    - Whether internet connectivity is currently available
    - Last model seeding timestamp
    - Whether models database has been seeded

    Used by frontend to display warnings when model downloads are unavailable.

    Args:
        startup_repo: Injected startup variables repository.

    Returns:
        ConnectionStatusResponse: Connection and seeding status information.

    Raises:
        DatabaseException: If database operation fails.

    Example:
        GET /startup/connection-status
        {
            "offline_mode": false,
            "can_download_models": true,
            "last_seeded_at": "2025-01-24T10:30:00Z",
            "models_seeded": true
        }
    """
    try:
        # Get or create singleton startup variables
        vars = startup_repo.get_or_create()
        
        # Check current internet connectivity
        current_online_status = is_online()
        
        logger.debug(
            f"Connection status: offline_mode={vars.offline_mode}, "
            f"can_download={current_online_status}, "
            f"models_seeded={vars.models_seeded}"
        )
        
        return ConnectionStatusResponse(
            offline_mode=vars.offline_mode,
            can_download_models=current_online_status,
            last_seeded_at=vars.last_seeded_at,
            models_seeded=vars.models_seeded
        )
        
    except Exception as e:
        logger.exception(f"Failed to get connection status: {e}")
        raise DatabaseException(
            "Failed to get connection status",
            trace=str(e)
        )
