import json

import pytest

from app.models import Session as ChatSession, User
from app.services import orchestrator


@pytest.mark.asyncio
async def test_chat_rag_answer_contains_policy(test_db, monkeypatch):
    with test_db() as db:
        user = User(username="visitor-rag", password_hash="")
        db.add(user)
        db.flush()
        session = ChatSession(user_id=user.id, title="新对话")
        db.add(session)
        db.commit()
        session_id = session.id

    # Fake the Milvus-backed RAG boundary while preserving the chunk text that was indexed.
    indexed_chunks: list[dict] = []
    monkeypatch.setattr("app.services.vector_store.upsert_chunks", lambda chunks, *_args: indexed_chunks.extend(chunks))
    monkeypatch.setattr("app.services.vector_store.search", lambda *_args, **_kwargs: [
        {"chunk_text": chunk["text"], "doc_name": "refund.md", "score": 0.1, "page": 1}
        for chunk in indexed_chunks
    ])
    indexed_chunks.append({"text": "退款政策：7 天无理由退款"})
    monkeypatch.setattr(orchestrator.llm_client, "classify_intent", _async_return("knowledge"))
    monkeypatch.setattr(orchestrator.rag_service, "retrieve", _async_return([
        {"doc_name": "refund.md", "snippet": "退款政策：7 天无理由退款"}
    ]))

    async def answer(_messages):
        yield "根据政策，支持 7 天无理由退款。"

    monkeypatch.setattr(orchestrator.llm_client, "chat_stream", answer)
    monkeypatch.setattr(orchestrator, "get_profile", lambda _visitor: {"style": "friendly", "length": "medium"})
    monkeypatch.setattr(orchestrator, "recall", _async_return([]))
    monkeypatch.setattr(orchestrator, "remember_turn", _async_return(None))
    events = [event async for event in orchestrator.handle_chat(str(session_id), "怎么退款", "rag")]
    assert any("7 天" in event.decode() for event in events)


def _async_return(value):
    async def _inner(*_args, **_kwargs):
        return value
    return _inner
