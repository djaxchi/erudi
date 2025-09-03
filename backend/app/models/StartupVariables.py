from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Float
from app.database import Base
from datetime import datetime


class StartupVariables(Base):
    __tablename__ = "startup_variables"

    id = Column(Integer, primary_key=True, index=True)
    welcome_popup_has_already_displayed = Column(Boolean, default=False, nullable=True)
