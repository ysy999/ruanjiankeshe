from collections.abc import Generator
import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.services import ingest_pipeline, knowledge_watcher, orchestrator

if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture
def test_db(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    knowledge_watcher.metadata.create_all(engine, tables=[knowledge_watcher.source_files])
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(orchestrator, "SessionLocal", factory)
    monkeypatch.setattr(ingest_pipeline, "SessionLocal", factory)
    monkeypatch.setattr(ingest_pipeline, "engine", engine)
    monkeypatch.setattr(knowledge_watcher, "SessionLocal", factory)
    yield factory
    engine.dispose()


@pytest.fixture
def app_client(test_db, monkeypatch: pytest.MonkeyPatch):
    from fastapi.testclient import TestClient

    from app.db import get_db
    from app.main import create_app

    def override_get_db() -> Generator:
        db = test_db()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    # Do not start external MCP, scheduler, database services, or network resources.
    client = TestClient(app, raise_server_exceptions=False)
    return client
