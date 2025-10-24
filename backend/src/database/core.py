"""SQLAlchemy database configuration and session management.

This module provides the core database infrastructure:
- Engine creation with SQLite configuration
- Session factory for transaction management
- Declarative base for ORM models
- Dependency injection helper for FastAPI endpoints

Configuration:
    - Database: SQLite at data/erudi.db (from DATABASE_URL env variable)
    - Thread Safety: check_same_thread=False for async FastAPI compatibility
    - Session Behavior: Manual commit/rollback (autocommit=False, autoflush=False)

Architecture:
    Database Layer:
    ┌────────────────────────────────────────────────────────┐
    │ FastAPI Endpoint                                       │
    │  └─> Depends(get_db) → yields SessionLocal instance   │
    └────────────────────────────────────────────────────────┘
                        ↓
    ┌────────────────────────────────────────────────────────┐
    │ Session (db)                                           │
    │  - db.query(Model).filter(...).all()                   │
    │  - db.add(instance)                                    │
    │  - db.commit() / db.rollback()                         │
    └────────────────────────────────────────────────────────┘
                        ↓
    ┌────────────────────────────────────────────────────────┐
    │ SQLite Engine (db_engine)                              │
    │  - Connection pooling                                  │
    │  - Transaction isolation                               │
    └────────────────────────────────────────────────────────┘

Example:
    Use in FastAPI endpoint::

        from fastapi import Depends
        from sqlalchemy.orm import Session
        from src.database.core import get_db
        from src.entities.Llm import Llm

        @router.get("/models")
        async def list_models(db: Session = Depends(get_db)):
            models = db.query(Llm).all()
            return {"models": models}

    Direct session usage (scripts, seeds)::

        from src.database.core import SessionLocal, Base, db_engine

        # Create tables
        Base.metadata.create_all(bind=db_engine)

        # Manual session
        db = SessionLocal()
        try:
            llm = Llm(name="Test", link="test/model")
            db.add(llm)
            db.commit()
        finally:
            db.close()

Note:
    - Always use get_db() for endpoint dependency injection
    - Manual sessions must be explicitly closed in finally blocks
    - Session is NOT thread-safe; create one per request

Warning:
    check_same_thread=False allows SQLite usage across threads but
    requires proper session isolation. Never share sessions across requests.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
# SQLite database URL
Path(".", "data").mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL")

# Create the SQLite engine
db_engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Create a session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

# Base class for models
Base = declarative_base()

# Dependency to get the database session
def get_db():
    """Provide database session for FastAPI dependency injection.

    Yields a SQLAlchemy session that is automatically closed after
    the request completes. Ensures proper cleanup even if exceptions occur.

    Yields:
        Session: Active database session bound to SQLite engine.

    Example:
        ::

            from fastapi import Depends, APIRouter
            from sqlalchemy.orm import Session
            from src.database.core import get_db

            router = APIRouter()

            @router.get("/users")
            async def get_users(db: Session = Depends(get_db)):
                users = db.query(User).all()
                return {"users": users}

    Note:
        Session is automatically closed in finally block. No manual cleanup needed.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()