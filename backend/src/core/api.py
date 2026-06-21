"""FastAPI application factory and lifecycle management.

This module provides the core FastAPI application configuration including:
- Router registration for all domain endpoints
- Exception handler setup for application-level errors
- CORS middleware configuration for cross-origin requests
- Application lifespan management (startup/shutdown hooks)

The lifespan context manager orchestrates:
1. Engine initialization and selection (MLX/CUDA/CPU)
2. Database table creation and seeding
3. Background cleanup tasks for model memory management

Architecture:
    Application Bootstrap Flow:
    ┌─────────────────────────────────────────────────────────────┐
    │ lifespan() startup:                                         │
    │  1. Select engine (MLX_Engine/CUDA_Engine/CPU_Engine)       │
    │  2. Create SQLAlchemy tables                                │
    │  3. Seed database with default models                       │
    │  4. Start cleanup task (30s interval)                       │
    └─────────────────────────────────────────────────────────────┘
                              ↓
    ┌─────────────────────────────────────────────────────────────┐
    │ register_routers():                                         │
    │  - /erudi/llms          → Model management                  │
    │  - /erudi/conversations → Chat/streaming                    │
    │  - /erudi/knowledge_base → RAG/vectorization                │
    │  - /erudi/arena         → Model comparison                  │
    │  - /erudi/hardware      → System monitoring                 │
    │  - /erudi/health        → Health checks                     │
    │  - /erudi/startup       → Initialization state              │
    └─────────────────────────────────────────────────────────────┘

Example:
    Create and configure the FastAPI application::

        from fastapi import FastAPI
        from src.core.api import (
            register_routers,
            add_exception_handlers,
            add_middleware,
            lifespan
        )

        app = FastAPI(lifespan=lifespan)
        register_routers(app)
        add_exception_handlers(app)
        add_middleware(app)

        # Run with: uvicorn src.main:app --reload

Note:
    The lifespan pattern ensures proper resource cleanup even if the
    application crashes or is forcefully terminated.
"""

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from src.database.core import init_database
from src.database.migrations import run_migrations
from src.database.seed import startup_populate_database
from src.launcher.postgres_runtime import start_postgres, stop_postgres
from src.ingestion.vector_store import close_kb_store, init_kb_store

from src.core.exceptions import AppBaseException, app_base_exception_handler
from src.core import config
from src.engines.base_engine import BaseEngine
from src.core.logging import logger
from src.agents.checkpoint import open_checkpointer

from src.domains.llms.endpoints import router as llms_router
from src.domains.arena.endpoints import router as arena_router
from src.domains.conversations.endpoints import router as conversations_router
from src.domains.hardware.endpoints import router as hardware_router
from src.domains.knowledge_base.endpoints import router as knowledge_base_router
from src.domains.startup.endpoints import router as startup_router
from src.core.health import router as health_router

def register_routers(app: FastAPI) -> None :
    """Register all domain routers to the FastAPI application.

    Attaches endpoint routers from each domain module with the /erudi prefix.
    Order of registration does not affect routing behavior due to FastAPI's
    path-matching algorithm.

    Args:
        app: The FastAPI application instance to register routers to.

    Returns:
        None. Modifies the app instance in-place.

    Example:
        ::

            from fastapi import FastAPI
            from src.core.api import register_routers

            app = FastAPI()
            register_routers(app)
            # All domain endpoints now accessible under /erudi/*
    """
    
    app.include_router(llms_router, prefix="/erudi")
    app.include_router(hardware_router, prefix="/erudi")
    app.include_router(arena_router, prefix="/erudi")
    app.include_router(knowledge_base_router, prefix="/erudi")
    app.include_router(conversations_router, prefix="/erudi")
    app.include_router(health_router, prefix="/erudi")
    app.include_router(startup_router, prefix="/erudi")

def add_exception_handlers(app: FastAPI) -> None :
    """Attach application-level exception handlers to FastAPI.

    Registers custom exception handlers for application-specific errors.
    Currently handles AppBaseException and its subclasses (ModelNotFoundException,
    InvalidInputException, EngineException).

    Args:
        app: The FastAPI application instance to attach handlers to.

    Returns:
        None. Modifies the app instance in-place.

    Example:
        ::

            from fastapi import FastAPI
            from src.core.api import add_exception_handlers

            app = FastAPI()
            add_exception_handlers(app)
            # Exceptions now return structured JSON responses with proper HTTP codes

    Note:
        See src.core.exceptions.app_base_exception_handler for response format.
    """
    app.add_exception_handler(AppBaseException, app_base_exception_handler)

def add_middleware(app: FastAPI) -> None:
    """Configure middleware for cross-origin resource sharing (CORS).

    Adds permissive CORS middleware to allow requests from any origin.
    Suitable for development and local desktop application environments.

    Args:
        app: The FastAPI application instance to configure.

    Returns:
        None. Modifies the app instance in-place.

    Example:
        ::

            from fastapi import FastAPI
            from src.core.api import add_middleware

            app = FastAPI()
            add_middleware(app)
            # Frontend at http://localhost:3000 can now access API

    Warning:
        Current configuration allows all origins ("*"). For production
        deployments, restrict allow_origins to specific trusted domains.
    """
    app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
    
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan with startup and shutdown hooks.

    This async context manager orchestrates the full application lifecycle:
    - Startup: Engine selection, database initialization, cleanup task scheduling
    - Shutdown: Task cancellation, engine cleanup, resource deallocation

    Args:
        app: The FastAPI application instance (passed by FastAPI framework).

    Yields:
        None. Control is yielded to the FastAPI application for request handling.

    Raises:
        Exception: Propagates any exception during startup (database errors,
            engine initialization failures). Application will not start if
            startup fails.

    Example:
        ::

            from fastapi import FastAPI
            from src.core.api import lifespan

            app = FastAPI(lifespan=lifespan)
            # Engine initialized automatically on startup
            # Cleanup runs automatically on shutdown

    Note:
        The cleanup task runs every 300 seconds to free inactive model memory.
        See BaseEngine.start_cleanup_task() for details.

    Lifecycle Flow:
        1. Start the embedded PostgreSQL cluster (postgres_runtime)
        2. Bind the SQLAlchemy engine/session factory (init_database)
        3. Select engine via platform detection (BaseEngine.get_engine)
        4. Migrate the schema to head (Alembic, forward-only)
        5. Seed database with default models (startup_populate_database)
        6. Open the LangGraph checkpointer (app.state.checkpointer)
        7. Start cleanup background task (300s interval)
        8. **[YIELD]** → Application handles requests
        9. Shutdown (reverse order): cleanup task → engine → checkpointer
           → embedded PostgreSQL cluster last
    """
    # Before yield comes the startup code
    logger.info("==== Starting up... ====")
    # Step 0: embedded PostgreSQL cluster — must precede any DB usage.
    app.state.postgres = start_postgres(config.POSTGRES_DATA_DIR)
    # Step 1: bind the SQLAlchemy engine/session factory to the live cluster.
    init_database(app.state.postgres.sqlalchemy_url)
    config.LLM_Engine = BaseEngine.get_engine()
    # Step 4: migrate the schema to head (forward-only). Alembic is sync, so run
    # it off the event loop. Replaces create_all — which never altered an existing
    # (persisted) database — and auto-adopts pre-Alembic schemas (stamp baseline).
    await run_in_threadpool(run_migrations, app.state.postgres)
    # await delete_all_data()
    await startup_populate_database()
    # Hybrid KB vector store (rag.kb_chunks) — AFTER the schema migration: its
    # cross-schema FKs reference the business tables.
    app.state.kb_store = init_kb_store(app.state.postgres)
    # LangGraph conversation-state checkpointer (AsyncPostgresSaver on the
    # same `erudi` database as the business schema), held open for the whole
    # app lifetime and exposed on app.state.checkpointer.
    checkpointer_cm = open_checkpointer(app.state.postgres.psycopg_url)
    app.state.checkpointer = await checkpointer_cm.__aenter__()
    config.LLM_Engine.start_cleanup_task()
    yield
    logger.info("==== Shutting down... ====")
    config.LLM_Engine.stop_cleanup_task()
    config.LLM_Engine.cleanup()
    await checkpointer_cm.__aexit__(None, None, None)
    close_kb_store()
    # Cluster stops LAST: every DB consumer above must be closed first.
    stop_postgres(app.state.postgres)
