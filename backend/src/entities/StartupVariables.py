"""SQLAlchemy entity for application startup state tracking.

Stores persistent UI state flags across app restarts, such as whether the welcome
popup has been shown, and model seeding state to avoid unnecessary API calls.

Example:
    from src.entities.StartupVariables import StartupVariables
    from datetime import datetime

    vars = StartupVariables(
        welcome_popup_has_already_displayed=True,
        models_seeded=True,
        last_seeded_at=datetime.now()
    )
"""
from sqlalchemy import Column, Integer, Boolean, DateTime
from sqlalchemy.orm import validates
from src.database.core import Base


class StartupVariables(Base):
    """SQLAlchemy model for application startup state persistence.

    Stores UI state flags and model seeding state that persist across app restarts.
    Singleton entity (only one row in table).

    Attributes:
        id: Primary key (singleton - only one row).
        welcome_popup_has_already_displayed: Boolean - True if welcome popup shown to user.
        models_seeded: Boolean - True if base/derived models have been seeded.
        last_seeded_at: DateTime - Timestamp of last successful model seeding.
        offline_mode: Boolean - True if last startup detected no internet connection.

    Constraints:
        - welcome_popup_has_already_displayed must be Boolean (enforced by validator).
        - models_seeded must be Boolean (enforced by validator).
        - offline_mode must be Boolean (enforced by validator).

    Example:
        >>> vars = db.query(StartupVariables).first()
        >>> if not vars.welcome_popup_has_already_displayed:
        ...     show_welcome_popup()
        ...     vars.welcome_popup_has_already_displayed = True
        ...     db.commit()
        >>> 
        >>> # Check if models need reseeding (every 3 days)
        >>> from datetime import datetime, timedelta
        >>> if not vars.models_seeded or (datetime.now() - vars.last_seeded_at) > timedelta(days=3):
        ...     await seed_models()
        ...     vars.models_seeded = True
        ...     vars.last_seeded_at = datetime.now()
        ...     db.commit()
    """
    __tablename__ = "startup_variables"

    id = Column(Integer, primary_key=True, index=True)
    welcome_popup_has_already_displayed = Column(Boolean, default=False, nullable=False)
    models_seeded = Column(Boolean, default=False, nullable=False)
    last_seeded_at = Column(DateTime, nullable=True)
    offline_mode = Column(Boolean, default=False, nullable=False)

    @validates('welcome_popup_has_already_displayed', 'models_seeded', 'offline_mode')
    def validate_boolean_flags(self, key, value):
        """Ensure boolean flags are actually Boolean type.

        Args:
            key: Column name being validated.
            value: Proposed Boolean value.

        Returns:
            bool: The validated Boolean value.

        Raises:
            ValueError: If value is not a Boolean.

        Example:
            >>> vars.models_seeded = True  # Valid
            >>> vars.models_seeded = "yes"  # Raises ValueError
        """
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be a Boolean, got {type(value)}")
        return value
