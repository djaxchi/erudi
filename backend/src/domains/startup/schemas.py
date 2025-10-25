"""Pydantic validation schemas for startup state management.

This module defines data transfer objects (DTOs) for the startup domain, handling
UI state persistence flags across application restarts.

Schema Purpose:
- WelcomePopupResponse: Response indicating if welcome popup should be shown.

Example:
    from src.domains.startup.schemas import WelcomePopupResponse
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/startup/welcome-popup", response_model=WelcomePopupResponse)
    def check_welcome_popup():
        return {"has_already_displayed": True}
"""
from pydantic import BaseModel, Field


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
