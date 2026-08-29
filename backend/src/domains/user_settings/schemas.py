"""Pydantic validation schemas for the user-settings domain (issue #310).

One singleton resource: the app-wide user settings. It carries the global
web-search default (#310) and the interface language (#385); new settings
slot in as additional fields.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

LanguageCode = Literal["en", "fr", "es", "zh"]


class UserSettingsResponse(BaseModel):
    """Response schema for the user-settings singleton.

    Attributes:
        web_search_enabled: Global default for the web_search agent tool.
            New conversations copy this value at creation; the per-conversation
            toggle owns it afterwards.
        language: Interface language code the frontend renders in.
    """
    web_search_enabled: bool = Field(
        ...,
        description="Global default for the web_search agent tool (new conversations inherit it)",
    )
    language: LanguageCode = Field(
        ...,
        description="Interface language code (en, fr, es, zh)",
    )

    class Config:
        from_attributes = True


class UserSettingsUpdate(BaseModel):
    """Request schema for updating the user-settings singleton (PUT).

    Partial update: every field is optional and an omitted field is left
    untouched, but an empty payload is rejected (nothing to update).
    """
    web_search_enabled: Optional[bool] = Field(
        None,
        description="Enable or disable the global web-search default",
    )
    language: Optional[LanguageCode] = Field(
        None,
        description="Interface language code (en, fr, es, zh)",
    )

    @model_validator(mode="after")
    def require_at_least_one_field(self):
        if self.web_search_enabled is None and self.language is None:
            raise ValueError("At least one setting must be provided")
        return self
