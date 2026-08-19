"""Pydantic validation schemas for the user-settings domain (issue #310).

One singleton resource: the app-wide user settings. Today it carries the
global web-search default; new settings slot in as additional fields.
"""
from pydantic import BaseModel, Field


class UserSettingsResponse(BaseModel):
    """Response schema for the user-settings singleton.

    Attributes:
        web_search_enabled: Global default for the web_search agent tool.
            New conversations copy this value at creation; the per-conversation
            toggle owns it afterwards.
    """
    web_search_enabled: bool = Field(
        ...,
        description="Global default for the web_search agent tool (new conversations inherit it)",
    )

    class Config:
        from_attributes = True


class UserSettingsUpdate(BaseModel):
    """Request schema for updating the user-settings singleton (PUT)."""
    web_search_enabled: bool = Field(
        ...,
        description="Enable or disable the global web-search default",
    )
