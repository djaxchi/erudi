from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import basic_routes
from .database import Base, engine
from .models.LLM import LLM
from sqlalchemy.orm import Session
from .database import SessionLocal
from pydantic import BaseModel

class LLMCreate(BaseModel):
    name: str
    local: int
    link: str

async def createTables():
    # Create all tables in the database
    Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    # Create tables on startup
    await createTables()
    
    # Mock local LLM data to test the database
    db: Session = SessionLocal()
    print(f"__________Mock before try:")

    try:
        # Mock LLM data
        model = LLMCreate(
            name="MockModel",
            local=1,  # 1 for local, 0 for remote
            link="data/mock_model"
        )
        
        # Add mock LLM to the database
        db_model = LLM(**model.dict())
        db.add(db_model)
        db.commit()
        db.refresh(db_model)
        print(f"__________Mock LLM added: {db_model}")
    finally:
        # Close the database session
        db.close()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],  # Allow all origins (you can restrict this to specific origins)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(basic_routes.router)
