from fastapi import APIRouter
from sqlalchemy import text

from app.db import engine
from app.exceptions import ChatException

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
def health_db() -> dict[str, str]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        raise ChatException(code=503, msg="database ping failed") from exc
    return {"status": "ok"}
