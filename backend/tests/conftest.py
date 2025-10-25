"""Pytest configuration and shared fixtures for all test modules.

Provides database session fixtures, test client, and mock data factories
following the repository pattern used in the codebase.

Architecture:
    Tests use in-memory SQLite database for isolation and speed.
    Each test gets a fresh database session with automatic rollback.
"""
import os
import sys
import pytest
import tempfile
from typing import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.database.core import Base
from src.main import app
from src.database.core import get_db


# ============ Database Fixtures ============

@pytest.fixture(scope="function")
def test_db_engine():
    """Create in-memory SQLite engine for testing.
    
    Yields:
        SQLAlchemy engine with all tables created.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_db_session(test_db_engine) -> Generator[Session, None, None]:
    """Create test database session with automatic rollback.
    
    Args:
        test_db_engine: SQLAlchemy engine fixture.
        
    Yields:
        Database session that rolls back after test.
    """
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_db_engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def client(test_db_session):
    """Create FastAPI test client with dependency injection.
    
    Overrides get_db dependency to use test database session.
    
    Args:
        test_db_session: Test database session fixture.
        
    Yields:
        FastAPI TestClient instance.
    """
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ============ Mock Data Fixtures ============

@pytest.fixture
def mock_llm(test_db_session):
    """Create mock base LLM for testing KB attachment.
    
    Args:
        test_db_session: Test database session.
        
    Returns:
        Llm entity with local=1, ready for KB attachment.
    """
    from src.entities.Llm import Llm
    
    llm = Llm(
        name="Test Base Model",
        description="Base model for testing",
        local=1,
        link="test/model/path",
        type="test",
        is_attached_to_kb=0,
        param_size=7.0,  # Float, not string
        quantized=1
    )
    test_db_session.add(llm)
    test_db_session.commit()
    test_db_session.refresh(llm)
    return llm


@pytest.fixture
def mock_llm_with_kb(test_db_session):
    """Create mock LLM with existing KB attachment.
    
    Args:
        test_db_session: Test database session.
        
    Returns:
        Tuple of (Llm, KnowledgeBase, VectorStore).
    """
    from src.entities.Llm import Llm
    from src.entities.KnowledgeBase import KnowledgeBase
    from src.entities.VectorStore import VectorStore
    
    # Create KB first
    kb = KnowledgeBase(
        file_names_list={"file_dropped_paths": ["/test/doc1.pdf"]},
        index_path="/test/index/1.index"
    )
    test_db_session.add(kb)
    test_db_session.flush()
    
    # Create LLM with KB attachment
    llm = Llm(
        name="Test Model with KB",
        description="Model with existing KB",
        local=1,
        link="test/model/path",
        type="test",
        is_attached_to_kb=1,
        kb_id=kb.id,
        param_size=7.0,  # Float, not string
        quantized=1
    )
    test_db_session.add(llm)
    test_db_session.flush()
    
    # Create VectorStore
    vector_store = VectorStore(
        kb_id=kb.id,
        vectors_data={"0": "test chunk"}
    )
    test_db_session.add(vector_store)
    test_db_session.commit()
    
    test_db_session.refresh(llm)
    test_db_session.refresh(kb)
    test_db_session.refresh(vector_store)
    
    return llm, kb, vector_store


@pytest.fixture
def temp_test_files():
    """Create temporary test files (PDF/TXT) for document ingestion.
    
    Yields:
        List of temporary file paths.
    """
    temp_files = []
    temp_dir = tempfile.mkdtemp()
    
    # Create test TXT file
    txt_path = os.path.join(temp_dir, "test_doc.txt")
    with open(txt_path, "w") as f:
        f.write("This is a test document for knowledge base testing. " * 50)
    temp_files.append(txt_path)
    
    yield temp_files
    
    # Cleanup
    for file_path in temp_files:
        if os.path.exists(file_path):
            os.remove(file_path)
    if os.path.exists(temp_dir):
        os.rmdir(temp_dir)


@pytest.fixture
def temp_index_dir():
    """Create temporary directory for FAISS indexes.
    
    Yields:
        Path to temporary index directory.
    """
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    
    # Cleanup
    for file in os.listdir(temp_dir):
        os.remove(os.path.join(temp_dir, file))
    os.rmdir(temp_dir)
