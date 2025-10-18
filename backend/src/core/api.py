from fastapi import FastAPI, APIRouter
from contextlib import asynccontextmanager
from src.database.seed import createTables, startup_populate_database
from src.core.exceptions import AppBaseException, app_base_exception_handler
from src.core.config import LLM_Engine
from src.core.logging import logger

download_llm_router = APIRouter(prefix="/llms", tags=["llms"])
training_router = APIRouter(prefix="/training", tags=["training"])
hardware_router = APIRouter(prefix="/hardware", tags=["hardware"])
arena_router = APIRouter(prefix="/arena", tags=["arena"])
knowledge_base_router = APIRouter(prefix="/knowledge_base", tags=["knowledge_base"])
conversations_router = APIRouter(prefix="/conversations", tags=["conversations"])
health_router = APIRouter(prefix="/health", tags=["health"])
startup_router = APIRouter(prefix="/startup", tags=["startup"])

def register_routers(app: FastAPI) -> None :
    app.include_router(download_llm_router, prefix="/erudi")
    app.include_router(training_router, prefix="/erudi")
    app.include_router(hardware_router, prefix="/erudi")
    app.include_router(arena_router, prefix="/erudi")
    app.include_router(knowledge_base_router, prefix="/erudi")
    app.include_router(conversations_router, prefix="/erudi")
    app.include_router(health_router, prefix="/erudi")
    app.include_router(startup_router, prefix="/erudi")

def add_exception_handlers(app: FastAPI) -> None :
    app.add_exception_handler(AppBaseException, app_base_exception_handler)


# TODO THE ENGINE CHOICE IN THE LIFESPAN
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Before yield comes the startup code
    logger.info("__________________________________ Starting up... __________________________________")
    await createTables()
    #await delete_all_data()
    await startup_populate_database()
    LLM_Engine.start_cleanup_task()
    yield
    logger.info("__________________________________ Shutting down... __________________________________")
    # Shutdown code can go here if needed
    LLM_Engine.stop_cleanup_task()
    LLM_Engine.cleanup()
