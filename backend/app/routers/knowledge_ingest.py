import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.ingest_pipeline import ingest
from app.services.knowledge_watcher import SOURCE_ROOT

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class IngestRequest(BaseModel):
    file_path: str


@router.post("/ingest")
async def ingest_document(payload: IngestRequest) -> dict[str, Any]:
    path = Path(payload.file_path).resolve()
    root = SOURCE_ROOT.resolve()
    if path != root and root not in path.parents:
        raise HTTPException(status_code=400, detail="file_path must be inside data/source_docs")
    if not path.is_file() or path.suffix.lower() not in {".md", ".txt", ".pdf"}:
        raise HTTPException(status_code=404, detail="supported source document not found")
    result = await asyncio.to_thread(ingest, str(path))
    return {"code": 0, "msg": "ingest completed", "data": result}
