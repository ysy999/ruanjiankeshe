"""Scheduled source-document and web-source change watcher."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from app.config import settings
from app.db import SessionLocal, engine

logger = logging.getLogger(__name__)
SOURCE_ROOT = Path(__file__).resolve().parents[3] / "data" / "source_docs"

metadata = MetaData()
source_files = Table(
    "source_files",
    metadata,
    Column("path", String(512), primary_key=True),
    Column("md5", String(32), nullable=False),
    Column("last_indexed_at", DateTime, nullable=True),
    Column("status", String(32), nullable=False, default="pending"),
    Column("chunk_count", Integer, nullable=False, default=0),
    Column("dropped_count", Integer, nullable=False, default=0),
)

_pending_paths: asyncio.Queue[str] = asyncio.Queue()
_scheduler: AsyncIOScheduler | None = None


def _digest(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()


def _store_source(path: str, digest: str) -> bool:
    """Upsert changed source metadata and report whether ingest is needed."""
    with SessionLocal() as db:
        previous = db.execute(select(source_files.c.md5, source_files.c.status).where(source_files.c.path == path)).first()
        if previous and previous.md5 == digest and previous.status in {"indexed", "pending", "processing"}:
            return False
        statement = mysql_insert(source_files).values(
            path=path, md5=digest, last_indexed_at=None, status="pending"
        ).on_duplicate_key_update(md5=digest, last_indexed_at=None, status="pending")
        db.execute(statement)
        db.commit()
        return True


async def _fetch_web_sources() -> list[Path]:
    saved: list[Path] = []
    if not settings.WEB_SOURCES:
        return saved
    web_root = SOURCE_ROOT / "web_sources"
    web_root.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for url in settings.WEB_SOURCES:
            try:
                response = await client.get(url)
                response.raise_for_status()
                name = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24] + ".txt"
                destination = web_root / name
                destination.write_text(response.text, encoding="utf-8")
                saved.append(destination)
            except Exception:
                logger.exception("抓取网页来源失败：%s", url)
    return saved


async def scan_sources() -> list[str]:
    """Scan local documents and configured web sources, queue changed paths."""
    SOURCE_ROOT.mkdir(parents=True, exist_ok=True)
    local_paths = [
        path for path in SOURCE_ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in {".md", ".txt", ".pdf"}
    ]
    web_paths = await _fetch_web_sources()
    queued: list[str] = []
    for path in [*local_paths, *web_paths]:
        try:
            digest = _digest(await asyncio.to_thread(path.read_bytes))
            normalized = str(path.resolve())
            if await asyncio.to_thread(_store_source, normalized, digest):
                await _pending_paths.put(normalized)
                queued.append(normalized)
        except Exception:
            logger.exception("扫描源文件失败：%s", path)
    return queued


async def iter_pending() -> AsyncIterator[str]:
    """Yield pending document paths for downstream ingestion workers."""
    while True:
        yield await _pending_paths.get()
        _pending_paths.task_done()


async def mark_indexed(path: str) -> None:
    """Mark a successfully ingested file as indexed."""
    with SessionLocal() as db:
        db.execute(
            source_files.update()
            .where(source_files.c.path == path)
            .values(status="indexed", last_indexed_at=datetime.utcnow())
        )
        db.commit()


async def _scheduled_scan_and_ingest() -> None:
    await scan_sources()
    # Import lazily to avoid a module cycle: ingest_pipeline also uses source_files.
    from app.services.ingest_pipeline import ingest

    while not _pending_paths.empty():
        path = await _pending_paths.get()
        try:
            await asyncio.to_thread(ingest, path)
        except Exception:
            logger.exception("定时 ingest 失败：%s", path)
        finally:
            _pending_paths.task_done()


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler
    metadata.create_all(bind=engine, tables=[source_files])
    _scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
    _scheduler.add_job(
        _scheduled_scan_and_ingest,
        "cron",
        hour=2,
        minute=0,
        id="knowledge-source-scan",
        replace_existing=True,
    )
    _scheduler.start()
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None


if __name__ == "__main__":
    async def _main() -> None:
        pending = await scan_sources()
        print(f"排入待处理队列：{len(pending)} 个文件")
        for path in pending:
            print(path)

    asyncio.run(_main())
