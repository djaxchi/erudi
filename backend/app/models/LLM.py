from sqlalchemy import Column, Integer, String
from .database import Base

class LLM(Base):
    __tablename__ = "llms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    path = Column(String, nullable=False)
    # defiines if the model is downloaded or not
    local = Column(Integer, nullable=False)
    # defines local path if model is local, huggingface link othewise
    link = Column(String, nullable=False)