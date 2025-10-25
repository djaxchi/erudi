"""Pydantic validation schemas for startup state management.

This module defines data transfer objects (DTOs) for the startup domain, handling
UI state persistence flags across application restarts.

Schema Purpose:
- WelcomePopupResponse: Response indicating if welcome popup should be shown.
- ConnectionStatusResponse: Response indicating online/offline mode and model seeding status.

Example:
    from src.domains.startup.schemas import WelcomePopupResponse, ConnectionStatusResponse
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/startup/welcome-popup", response_model=WelcomePopupResponse)
    def check_welcome_popup():
        return {"has_already_displayed": True}
    
    @app.get("/startup/connection-status", response_model=ConnectionStatusResponse)
    def get_connection_status():
        return {
            "offline_mode": False,
            "can_download_models": True,
            "last_seeded_at": "2025-01-24T10:30:00"
        }
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class WelcomePopupResponse(BaseModel):
    """Response schema for welcome popup display status.

    Indicates whether the welcome popup has already been shown to the user.
    Used by frontend to determine if popup should be displayed.

    Attributes:
        has_already_displayed: True if popup was already shown, False if first time.

    Example:
        >>> response = WelcomePopupResponse(has_already_displayed=False)
        >>> print(response.has_already_displayed)
        False
    """
    has_already_displayed: bool = Field(
        ...,
        description="True if welcome popup already shown, False if first time"
    )

    class Config:
        """Pydantic configuration for WelcomePopupResponse model.
        
        Enables JSON schema generation for OpenAPI documentation.
        """
        json_schema_extra = {
            "example": {
                "has_already_displayed": False
            }
        }


class ConnectionStatusResponse(BaseModel):
    """Response schema for application connection and model seeding status.

    Provides information about online/offline mode and whether the app can download
    new models from Hugging Face. Used by frontend to display warnings when offline.

    Attributes:
        offline_mode: True if app last seeded in offline mode (from JSON fallback).
        can_download_models: True if app has internet connectivity to Hugging Face.
        last_seeded_at: Timestamp of last model database seeding (None if never seeded).
        models_seeded: True if model database has been seeded at least once.

    Example:
        >>> response = ConnectionStatusResponse(
        ...     offline_mode=True,
        ...     can_download_models=False,
        ...     last_seeded_at=datetime.utcnow(),
        ...     models_seeded=True
        ... )
        >>> print(response.offline_mode)
        True
    """
    offline_mode: bool = Field(
        ...,
        description="True if last seeded in offline mode (from JSON fallback)"
    )
    can_download_models: bool = Field(
        ...,
        description="True if internet connectivity available for model downloads"
    )
    last_seeded_at: Optional[datetime] = Field(
        None,
        description="Timestamp of last model seeding (None if never seeded)"
    )
    models_seeded: bool = Field(
        ...,
        description="True if models database has been seeded at least once"
    )

    class Config:
        """Pydantic configuration for ConnectionStatusResponse model.
        
        Enables JSON schema generation for OpenAPI documentation.
        """
        json_schema_extra = {
            "example": {
                "offline_mode": False,
                "can_download_models": True,
                "last_seeded_at": "2025-01-24T10:30:00Z",
                "models_seeded": True
            }
        }
