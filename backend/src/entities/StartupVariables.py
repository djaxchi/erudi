"""SQLAlchemy entity for application startup state tracking.

Stores persistent UI state flags across app restarts, such as whether the welcome
popup has been shown. Singleton entity (only one row).

Example:
    from src.entities.StartupVariables import StartupVariables

    vars = StartupVariables(welcome_popup_has_already_displayed=True)
"""
from sqlalchemy import Column, Integer, Boolean
from sqlalchemy.orm import validates
from src.database.core import Base


class StartupVariables(Base):
    """SQLAlchemy model for application startup state persistence.

    Stores UI state flags that persist across app restarts, such as welcome popup
    display status. Singleton entity (only one row in table).

    Attributes:
        id: Primary key (singleton - only one row).
        welcome_popup_has_already_displayed: Boolean - True if welcome popup shown to user.

    Constraints:
        - welcome_popup_has_already_displayed must be Boolean (enforced by validator).

    Example:
        >>> vars = db.query(StartupVariables).first()
        >>> if not vars.welcome_popup_has_already_displayed:
        ...     show_welcome_popup()
        ...     vars.welcome_popup_has_already_displayed = True
        ...     db.commit()
    """
    __tablename__ = "startup_variables"

    id = Column(Integer, primary_key=True, index=True)
    welcome_popup_has_already_displayed = Column(Boolean, default=False, nullable=False)

    @validates('welcome_popup_has_already_displayed')
    def validate_welcome_popup_flag(self, key, value):
        """Ensure welcome_popup_has_already_displayed is Boolean type.

        Args:
            key: Column name being validated ('welcome_popup_has_already_displayed').
            value: Proposed Boolean value.

        Returns:
            bool: The validated Boolean value.

        Raises:
            ValueError: If value is not Boolean type.
        """
        if not isinstance(value, bool):
            raise ValueError(f"welcome_popup_has_already_displayed must be Boolean, got {type(value).__name__}")
        return value

    __table_args__ = (
        {"sqlite_autoincrement": True}
    )
