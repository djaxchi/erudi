"""FastAPI endpoints for the user-settings singleton (issue #310).

GET/PUT ``/erudi/user_settings/``: the app-wide settings the frontend's
Settings page binds to. Today: the global web-search default. Follows the
startup domain's layering (endpoints -> repository) — the resource is a
one-row singleton with no business logic beyond get-or-create.
"""
from fastapi import Depends, APIRouter
from sqlalchemy.orm import Session

from src.database.core import get_db
from src.domains.user_settings.repository import User_Settings_Repository
from src.domains.user_settings.schemas import UserSettingsResponse, UserSettingsUpdate
from src.core.logging import logger
from src.core.exceptions import DatabaseException

router = APIRouter(prefix="/user_settings", tags=["user_settings"])


def get_user_settings_repository(
    db: Session = Depends(get_db),
) -> User_Settings_Repository:
    """FastAPI dependency injection factory for User_Settings_Repository."""
    return User_Settings_Repository(db)


@router.get("/", response_model=UserSettingsResponse)
async def get_user_settings(
    settings_repo: User_Settings_Repository = Depends(get_user_settings_repository),
    db: Session = Depends(get_db),
):
    """Fetch the user-settings singleton (created with defaults on first read).

    Example:
        GET /erudi/user_settings/ -> {"web_search_enabled": false}
    """
    try:
        settings = settings_repo.get_or_create()
        db.commit()
        return settings
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to get user settings: {e}")
        raise DatabaseException("Failed to get user settings", trace=str(e))


@router.put("/", response_model=UserSettingsResponse)
async def update_user_settings(
    payload: UserSettingsUpdate,
    settings_repo: User_Settings_Repository = Depends(get_user_settings_repository),
    db: Session = Depends(get_db),
):
    """Update the user-settings singleton.

    Example:
        PUT /erudi/user_settings/ {"web_search_enabled": true}
        -> {"web_search_enabled": true}
    """
    try:
        settings = settings_repo.get_or_create()
        settings_repo.set_web_search_enabled(settings, payload.web_search_enabled)
        db.commit()
        logger.info(
            f"User settings updated: web_search_enabled={payload.web_search_enabled}"
        )
        return settings
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to update user settings: {e}")
        raise DatabaseException("Failed to update user settings", trace=str(e))
