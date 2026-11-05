import pytest

from app.models import Session as ChatSession, User
from app.services import orchestrator


@pytest.mark.asyncio
async def test_mcp_failure_is_explained_in_sse(test_db, monkeypatch):
    with test_db() as db:
        user = User(username="visitor-mcp", password_hash="")
        db.add(user)
        db.flush()
        session = ChatSession(user_id=user.id, title="新对话")
        db.add(session)
        db.commit()
        session_id = session.id

    async def intent(_messages): return "order"
    async def fail_tool(*_args, **_kwargs): raise RuntimeError("MCP unavailable")
    async def no_memory(*_args, **_kwargs): return []
    async def no_remember(*_args, **_kwargs): return None
    async def response(messages):
        assert "订单系统暂时查询失败" in messages[0]["content"]
        yield "订单系统暂时查询失败，请稍后再试。"

    monkeypatch.setattr(orchestrator.llm_client, "classify_intent", intent)
    monkeypatch.setattr(orchestrator.mcp_client, "call_tool", fail_tool)
    monkeypatch.setattr(orchestrator.llm_client, "chat_stream", response)
    monkeypatch.setattr(orchestrator, "get_profile", lambda _visitor: {"style": "friendly", "length": "medium"})
    monkeypatch.setattr(orchestrator, "recall", no_memory)
    monkeypatch.setattr(orchestrator, "remember_turn", no_remember)
    events = [event async for event in orchestrator.handle_chat(str(session_id), "订单 O20261001001 到哪了", "mcp")]
    assert any("订单系统暂时查询失败" in event.decode() for event in events)
