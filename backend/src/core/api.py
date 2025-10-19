from fastapi import FastAPI
from contextlib import asynccontextmanager
from src.database.seed import createTables, startup_populate_database

from src.core.exceptions import AppBaseException, app_base_exception_handler
from src.core import vars
from src.engines.base_engine import BaseEngine
from src.core.logging import logger

from src.domains.llms.endpoints import router as llms_router
from src.domains.arena.endpoints import router as arena_router
from src.domains.conversations.endpoints import router as conversations_router
from src.domains.hardware.endpoints import router as hardware_router
from src.domains.knowledge_base.endpoints import router as knowledge_base_router
from src.domains.startup.endpoints import router as startup_router
from src.domains.training.endpoints import router as training_router
from src.core.health import router as health_router

def register_routers(app: FastAPI) -> None :
    
    app.include_router(llms_router, prefix="/erudi")
    app.include_router(training_router, prefix="/erudi")
    app.include_router(hardware_router, prefix="/erudi")
    app.include_router(arena_router, prefix="/erudi")
    app.include_router(knowledge_base_router, prefix="/erudi")
    app.include_router(conversations_router, prefix="/erudi")
    app.include_router(health_router, prefix="/erudi")
    app.include_router(startup_router, prefix="/erudi")

def add_exception_handlers(app: FastAPI) -> None :
    app.add_exception_handler(AppBaseException, app_base_exception_handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Before yield comes the startup code
    logger.info("==== Starting up... ====")
    vars.LLM_Engine = BaseEngine.get_engine()
    await createTables()
    #await delete_all_data()
    await startup_populate_database()
    vars.LLM_Engine.start_cleanup_task()
    yield
    logger.info("==== Shutting down... ====")
    # Shutdown code can go here if needed
    vars.LLM_Engine.stop_cleanup_task()
    vars.LLM_Engine.cleanup()
