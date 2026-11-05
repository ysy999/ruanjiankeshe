from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.services.mcp_client import mcp_client
from app.services.knowledge_watcher import start_scheduler, stop_scheduler


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        start_scheduler()
        try:
            await mcp_client.connect()
        except Exception:
            # Keep HTTP APIs available if the optional MCP subprocess is unavailable.
            pass
        try:
            yield
        finally:
            await mcp_client.close()
            stop_scheduler()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router)
    return app

