from fastapi import APIRouter

from app.api import health
from app.routers import chat_router, feedback_router, knowledge_ingest_router, metrics_router, mcp_test_router, profile_router, sessions_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(sessions_router)
api_router.include_router(chat_router)
api_router.include_router(profile_router)
api_router.include_router(mcp_test_router)
api_router.include_router(knowledge_ingest_router)
api_router.include_router(feedback_router)
api_router.include_router(metrics_router)
