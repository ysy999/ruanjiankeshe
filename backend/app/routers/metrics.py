from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import CallLog

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
def get_metrics(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(
        select(CallLog)
        .where(CallLog.tool_name == "chat_metrics")
        .order_by(CallLog.created_at.desc(), CallLog.id.desc())
        .limit(100)
    ).all()
    count = len(rows)
    return {
        "code": 0,
        "msg": "ok",
        "data": {
            "avg_total_ms": round(sum(row.latency_ms or 0 for row in rows) / count, 2) if count else 0,
            "avg_retrieve_ms": round(sum((row.params or {}).get("retrieve_ms", 0) for row in rows) / count, 2) if count else 0,
            "success_rate": round(sum(bool((row.result or {}).get("success")) for row in rows) / count, 4) if count else 0,
            "sample_count": count,
        },
    }
