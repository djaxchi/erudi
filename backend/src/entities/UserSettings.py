"""SQLAlchemy entity for global user settings.

Singleton table (one row) holding app-wide user preferences, mirroring the
``StartupVariables`` singleton pattern. First occupant: the global web-search
toggle (issue #310) — the DEFAULT for new conversations. Each conversation
copies this value at creation and owns its flag afterwards; changing the
global setting never retro-affects existing conversations.

Example:
    from src.entities.UserSettings import UserSettings

    settings = UserSettings(web_search_enabled=False)
"""
from sqlalchemy import Column, Integer, Boolean, String
from sqlalchemy.orm import validates
from src.database.core import Base

# The four interface languages the frontend ships translations for (#385).
# The list is the single source of truth for the schema Literal and the
# entity validator; the frontend mirrors it in src/i18n/languages.js.
SUPPORTED_LANGUAGES = ("en", "fr", "es", "zh")
DEFAULT_LANGUAGE = "en"


class UserSettings(Base):
    """SQLAlchemy model for the user-settings singleton.

    Attributes:
        id: Primary key (singleton - only one row).
        web_search_enabled: Boolean - global default for the web_search agent
            tool (#310). False by default: a web search egresses the user's
            query, so the local-first product keeps it strictly opt-in.
        language: Interface language code (#385), one of SUPPORTED_LANGUAGES.
            "en" by default; the frontend derives the first value from the OS
            locale and persists it here so it survives restarts.

    Constraints:
        - web_search_enabled must be a Boolean (enforced by validator).
        - language must be one of SUPPORTED_LANGUAGES (enforced by validator).
    """
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    web_search_enabled = Column(Boolean, default=False, nullable=False)
    language = Column(String(8), default=DEFAULT_LANGUAGE, nullable=False)

    @validates('language')
    def validate_language(self, key, value):
        """Ensure the language is one of the supported interface languages.

        Raises:
            ValueError: If value is not in SUPPORTED_LANGUAGES.
        """
        if value not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"{key} must be one of {SUPPORTED_LANGUAGES}, got {value!r}"
            )
        return value

    @validates('web_search_enabled')
    def validate_boolean_flags(self, key, value):
        """Ensure boolean flags are actually Boolean type.

        Args:
            key: Column name being validated.
            value: Proposed Boolean value.

        Returns:
            bool: The validated Boolean value.

        Raises:
            ValueError: If value is not a Boolean.
        """
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be a Boolean, got {type(value)}")
        return value
