"""Data access layer for the UserSettings singleton (issue #310).

Mirrors ``Startup_Variables_Repository``: get-or-create on a one-row table,
mutations flushed (not committed) so the caller controls the transaction.
"""

from sqlalchemy.orm import Session

from src.entities.UserSettings import DEFAULT_LANGUAGE, UserSettings
from src.core.logging import logger


class User_Settings_Repository:
    """Repository for the UserSettings singleton entity.

    Attributes:
        db: SQLAlchemy database session (injected by FastAPI).
    """

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db
        logger.debug("Initializing User_Settings_Repository")

    def get_or_create(self) -> UserSettings:
        """Retrieve the singleton UserSettings record, creating if absent.

        Returns:
            UserSettings: The singleton settings entity (defaults applied on
            first creation: web_search_enabled=False, language="en").
        """
        settings = self.db.query(UserSettings).first()
        if not settings:
            logger.info("UserSettings not found, creating singleton with defaults")
            settings = UserSettings(web_search_enabled=False, language=DEFAULT_LANGUAGE)
            self.db.add(settings)
            self.db.flush()
            self.db.refresh(settings)
        return settings

    def get_web_search_enabled(self) -> bool:
        """The global web-search default (False until the user opts in).

        Read-only: callers on hot paths (conversation creation, arena turns)
        must not write; a missing singleton row IS the default.
        """
        settings = self.db.query(UserSettings).first()
        return bool(settings.web_search_enabled) if settings else False

    def set_web_search_enabled(self, settings: UserSettings, value: bool) -> UserSettings:
        """Update the global web-search default (flushed, not committed).

        Args:
            settings: The singleton entity to update.
            value: New Boolean value.

        Returns:
            UserSettings: Updated entity.
        """
        logger.info(f"Updating UserSettings.web_search_enabled = {value}")
        settings.web_search_enabled = value
        self.db.flush()
        self.db.refresh(settings)
        return settings

    def set_language(self, settings: UserSettings, value: str) -> UserSettings:
        """Update the interface language (flushed, not committed).

        Args:
            settings: The singleton entity to update.
            value: One of the supported language codes (validated by the entity).

        Returns:
            UserSettings: Updated entity.
        """
        logger.info(f"Updating UserSettings.language = {value}")
        settings.language = value
        self.db.flush()
        self.db.refresh(settings)
        return settings
