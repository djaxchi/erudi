from fastapi import FastAPI
from src.core.api import register_routers, lifespan, add_exception_handlers, add_middleware

app = FastAPI(lifespan=lifespan, title="erudi", version="0.1.0")
add_middleware(app=app)
add_exception_handlers(app=app)
register_routers(app=app)