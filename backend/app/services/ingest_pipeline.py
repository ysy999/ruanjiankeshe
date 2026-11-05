"""Document chunk filtering, exact deduplication and ingest counters."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, select, update

from app.db import SessionLocal, engine
from app.services.chunker import load_document
from app.services.knowledge_watcher import metadata as watcher_metadata, source_files

logger = logging.getLogger(__name__)
MIN_CHUNK_LENGTH = 50
doc_versions = Table(
    "doc_versions",
    watcher_metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("doc_name", String(512), nullable=False),
    Column("version", String(32), nullable=False),
    Column("status", String(32), nullable=False, default="active"),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
)


def process_document(file_path: str) -> list[dict]:
    """Load and filter document chunks, deduplicate exact text, and persist counts."""
    chunks = load_document(file_path)
    valid_chunks: list[dict] = []
    seen_hashes: set[str] = set()
    dropped_count = 0

    for chunk in chunks:
        text = str(chunk.get("text", "")).strip()
        if len(text) < MIN_CHUNK_LENGTH:
            dropped_count += 1
            logger.info("丢弃过短 chunk：file=%s index=%s length=%d", file_path, chunk.get("chunk_index"), len(text))
            continue

        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if digest in seen_hashes:
            dropped_count += 1
            logger.info("丢弃重复 chunk：file=%s index=%s hash=%s", file_path, chunk.get("chunk_index"), digest)
            continue
        seen_hashes.add(digest)
        valid_chunks.append({**chunk, "text": text})

    try:
        normalized_path = str(Path(file_path).resolve())
        with SessionLocal() as db:
            db.execute(
                update(source_files)
                .where(source_files.c.path == normalized_path)
                .values(chunk_count=len(valid_chunks), dropped_count=dropped_count)
            )
            db.commit()
    except Exception:
        logger.exception("写入 source_files chunk 计数失败：%s", file_path)
        raise

    logger.info(
        "文档分块处理完成：file=%s chunk_count=%d dropped_count=%d",
        file_path,
        len(valid_chunks),
        dropped_count,
    )
    return valid_chunks


def ingest(file_path: str) -> dict:
    """Chunk, embed and index a source document, retaining its prior version."""
    from app.services.embedding_client import EmbeddingClient
    from app.services.vector_store import mark_deprecated, upsert_chunks

    watcher_metadata.create_all(bind=engine, tables=[doc_versions])
    document = Path(file_path)
    normalized_path = str(document.resolve())
    doc_name = document.name

    with SessionLocal() as db:
        previous = db.execute(
            select(doc_versions.c.version)
            .where(doc_versions.c.doc_name == doc_name, doc_versions.c.status == "active")
            .order_by(doc_versions.c.created_at.desc(), doc_versions.c.id.desc())
            .limit(1)
        ).first()
        old_version = previous.version if previous else None

    try:
        chunks = process_document(normalized_path)
        embeddings = EmbeddingClient().embed_texts([chunk["text"] for chunk in chunks])
        new_version = datetime.now().strftime("%Y%m%d%H%M%S")
        upsert_chunks(chunks, embeddings, doc_name, new_version)

        if old_version:
            mark_deprecated(doc_name, old_version)
        with SessionLocal() as db:
            if old_version:
                db.execute(
                    update(doc_versions)
                    .where(doc_versions.c.doc_name == doc_name, doc_versions.c.version == old_version)
                    .values(status="deprecated")
                )
            db.execute(doc_versions.insert().values(
                doc_name=doc_name,
                version=new_version,
                status="active",
                created_at=datetime.utcnow(),
            ))
            db.execute(
                update(source_files)
                .where(source_files.c.path == normalized_path)
                .values(
                    status="indexed",
                    last_indexed_at=datetime.utcnow(),
                    chunk_count=len(chunks),
                )
            )
            db.commit()
        logger.info("文档 ingest 完成：file=%s version=%s chunks=%d", normalized_path, new_version, len(chunks))
        return {"doc_name": doc_name, "version": new_version, "chunk_count": len(chunks)}
    except Exception:
        logger.exception("文档 ingest 失败：%s", normalized_path)
        with SessionLocal() as db:
            db.execute(update(source_files).where(source_files.c.path == normalized_path).values(status="failed"))
            db.commit()
        raise
