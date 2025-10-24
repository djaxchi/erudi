"""SQLAlchemy entity for application startup state tracking.

Stores persistent UI state flags across app restarts, such as whether the welcome
popup has been shown. Singleton entity (only one row).

Example:
    from src.entities.StartupVariables import StartupVariables

    vars = StartupVariables(welcome_popup_has_already_displayed=True)
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Float
from src.database.core import Base
from datetime import datetime


class StartupVariables(Base):
    """SQLAlchemy model for application startup state persistence.

    Stores UI state flags that persist across app restarts, such as welcome popup
    display status. Singleton entity (only one row in table).

    Attributes:
        id: Primary key (singleton - only one row).
        welcome_popup_has_already_displayed: True if welcome popup shown to user.

    Example:
        >>> vars = db.query(StartupVariables).first()
        >>> if not vars.welcome_popup_has_already_displayed:
        ...     show_welcome_popup()
        ...     vars.welcome_popup_has_already_displayed = True
        ...     db.commit()
    """
    __tablename__ = "startup_variables"

    id = Column(Integer, primary_key=True, index=True)
    welcome_popup_has_already_displayed = Column(Boolean, default=False, nullable=True)
