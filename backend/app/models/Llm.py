from sqlalchemy import Column, Integer, String
from ..database import Base

class Llm(Base):
    __tablename__ = "llms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    # defiines if the model is downloaded or not
    local = Column(Integer, nullable=False)
    # defines local path if model is local, huggingface link othewise
    link = Column(String, nullable=True)