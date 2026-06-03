"""Pytest configuration and shared fixtures for all test modules.

Provides database session fixtures, test client, and mock data factories
following the repository pattern used in the codebase.

Architecture:
    Tests use in-memory SQLite database for isolation and speed.
    Each test gets a fresh database session with automatic rollback.
"""
# Force the multiprocessing start method to "spawn" BEFORE any heavy import
# below loads modules that would interact with multiprocessing internals.
# This mirrors `backend/run.py:force_mp_spawn()` and is required because:
#   1. The MLX engine refactor will use `multiprocessing.Process` to spawn
#      `mlx_lm.server` as a child process. Spawn is the only start method
#      that works inside PyInstaller frozen builds (`mp.freeze_support()`).
#   2. On Linux (CI), the default is `fork`, which after importing torch /
#      faiss / sentence_transformers has undefined behaviour.
#   3. Setting `force=True` here makes the test environment match production.
import multiprocessing as _mp

try:
    _mp.set_start_method("spawn", force=True)
except RuntimeError:
    # Already configured (e.g. pytest re-execution) — safe to ignore.
    pass

import os
import sys
import pytest
import tempfile
from typing import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.database.core import Base
from src.main import app
from src.database.core import get_db

from tests._helpers import is_mlx_platform


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
    """Create test database session with savepoint-based nested transactions.
    
    Uses SAVEPOINT to allow code under test to call commit() without affecting
    the outer test transaction. All changes are rolled back at test completion.
    
    Args:
        test_db_engine: SQLAlchemy engine fixture.
        
    Yields:
        Database session that supports nested transactions via savepoints.
    """
    connection = test_db_engine.connect()
    transaction = connection.begin()  # Outer transaction
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=connection
    )
    session = TestingSessionLocal(bind=connection)
    
    # Begin nested transaction (savepoint)
    nested = connection.begin_nested()
    
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        """Automatically restart savepoint after each commit."""
        if transaction.nested and not transaction._parent.nested:
            # Re-establish savepoint after inner transaction ends
            session.begin_nested()
    
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()  # Roll back everything
        connection.close()


@pytest.fixture(scope="function")
def client(test_db_session):
    """Create FastAPI test client with dependency injection.
    
    Overrides get_db dependency to use test database session.
    Creates app without lifespan to avoid production DB interactions.
    
    Args:
        test_db_session: Test database session fixture.
        
    Yields:
        FastAPI TestClient instance.
    """
    from fastapi import FastAPI
    from src.core.api import register_routers, add_exception_handlers, add_middleware
    from src.engines.base_engine import BaseEngine
    from src.core import config
    
    # Create app WITHOUT lifespan
    test_app = FastAPI(title="Erudi Test", version="0.1.0")
    add_middleware(app=test_app)
    add_exception_handlers(app=test_app)
    register_routers(app=test_app)
    
    # Override get_db to use test session
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass
    
    test_app.dependency_overrides[get_db] = override_get_db
    
    # Initialize engine for tests
    if not config.LLM_Engine:
        config.LLM_Engine = BaseEngine.get_engine()

    # Provide an in-memory checkpointer (production lifespan is bypassed here).
    from langgraph.checkpoint.memory import InMemorySaver
    test_app.state.checkpointer = InMemorySaver()

    with TestClient(test_app, raise_server_exceptions=False) as test_client:
        yield test_client
    
    test_app.dependency_overrides.clear()


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
        is_attached_to_kb=False,  # Boolean
        param_size=7.0,
        quantized=True  # Boolean
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
        is_attached_to_kb=True,  # Boolean
        kb_id=kb.id,
        param_size=7.0,
        quantized=True  # Boolean
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


# ============ MLX-specific fixtures (Phase 0 — refactor/mlx-server-subprocess) ============
#
# Shared infrastructure for the MLX server-mode refactor test suite. These
# fixtures are session-scoped to amortize the cost of downloading the test
# models across the whole suite, and skip cleanly on non-Apple-Silicon hosts
# so that Linux CI stays green.
#
# Two models are provided:
#
#   `mlx_test_model_path` — default, always available
#       repo: mlx-community/Qwen2.5-0.5B-Instruct-4bit
#       - Apache 2.0 (no HF license accept required, works in unattended CI)
#       - 4-bit quantized, ~280 MB on disk
#       - No <think> tokens (keeps text-only assertions simple)
#       - Standard ChatML template (validates apply_chat_template path)
#
#   `mlx_thinking_model_path` — opt-in via ERUDI_TEST_THINKING=1
#       repo: mlx-community/Qwen3-0.6B-4bit (override: ERUDI_MLX_THINKING_MODEL_REPO)
#       - Required to validate that `reasoning_text` is delivered as a
#         separate stream channel by mlx_lm.server (i.e. the refactor does
#         not silently drop reasoning output).
#       - Without this fixture, the regression of `<think>...</think>` /
#         `<|channel>thought ... <channel|>` filtering would be invisible.
#
# Gemma-specific EOS regression coverage is opt-in via ERUDI_TEST_GEMMA=1
# (added in Phase 1 once we have the corresponding test).

MLX_TEST_MODEL_REPO = "mlx-community/Qwen2.5-0.5B-Instruct-4bit"
MLX_TEST_THINKING_MODEL_REPO_DEFAULT = "mlx-community/Qwen3-0.6B-4bit"


def _download_mlx_model(repo_id: str, local_dir_env_var: str | None = None) -> Path:
    """Download (or reuse cache for) an MLX-quantized model from the HF Hub.

    Returns the absolute local path as a `Path`. Skips the calling test on:
      - non-MLX platforms (Linux CI, Mac Intel, etc.)
      - missing huggingface_hub
      - network failure with no local cache (offline dev)

    Args:
        repo_id: HF repo id, e.g. "mlx-community/Qwen2.5-0.5B-Instruct-4bit".
        local_dir_env_var: optional env var name that, if set and non-empty,
            overrides the HF cache directory for offline / pre-seeded setups.
    """
    if not is_mlx_platform():
        pytest.skip("MLX_Engine not selected on this platform — MLX fixture skipped")

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        pytest.skip(f"huggingface_hub not available: {exc}")

    # Treat "" as None so an unset env var doesn't get passed as an empty path.
    override = os.environ.get(local_dir_env_var) if local_dir_env_var else None
    local_dir = override or None

    try:
        local_path = snapshot_download(repo_id=repo_id, local_dir=local_dir)
    except Exception as exc:
        # Covers LocalEntryNotFoundError, HfHubHTTPError, ConnectionError, etc.
        # On offline runs with cold cache we skip rather than ERROR so the
        # rest of the suite is not blocked.
        pytest.skip(f"Cannot fetch MLX test model {repo_id!r} (offline?): {exc}")

    return Path(local_path)


@pytest.fixture(scope="session")
def mlx_test_model_path() -> Path:
    """Local path to the default MLX test model (no thinking tokens).

    See module-level comment for repo details and rationale.
    """
    return _download_mlx_model(
        MLX_TEST_MODEL_REPO,
        local_dir_env_var="ERUDI_MLX_TEST_MODEL_DIR",
    )


@pytest.fixture(scope="session")
def mlx_thinking_model_path() -> Path:
    """Local path to an MLX test model that emits `<think>` tokens.

    Opt-in via ERUDI_TEST_THINKING=1 to keep the default suite fast. The repo
    can be overridden via ERUDI_MLX_THINKING_MODEL_REPO for forward
    compatibility (e.g. when newer thinking-capable MLX repos appear).
    """
    if os.environ.get("ERUDI_TEST_THINKING") != "1":
        pytest.skip(
            "Thinking-model integration tests are opt-in. "
            "Run with ERUDI_TEST_THINKING=1 to enable."
        )

    repo_id = os.environ.get(
        "ERUDI_MLX_THINKING_MODEL_REPO",
        MLX_TEST_THINKING_MODEL_REPO_DEFAULT,
    )
    return _download_mlx_model(
        repo_id,
        local_dir_env_var="ERUDI_MLX_THINKING_MODEL_DIR",
    )
