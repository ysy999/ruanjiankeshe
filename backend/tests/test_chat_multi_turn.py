import json

import pytest

from app.models import Message, Session as ChatSession, User
from app.services import orchestrator


@pytest.mark.asyncio
async def test_second_turn_reuses_prior_order_id(test_db, monkeypatch):
    with test_db() as db:
        user = User(username="visitor-multi", password_hash="")
        db.add(user)
        db.flush()
        session = ChatSession(user_id=user.id, title="新对话")
        db.add(session)
        db.commit()
        session_id = session.id

    monkeypatch.setattr(orchestrator, "get_profile", lambda _visitor: {"style": "friendly", "length": "medium"})
    async def noop(*_args, **_kwargs): return []
    async def remember(*_args, **_kwargs): return None
    monkeypatch.setattr(orchestrator, "recall", noop)
    monkeypatch.setattr(orchestrator, "remember_turn", remember)
    monkeypatch.setattr(orchestrator.llm_client, "classify_intent", _intent_order)
    called: list[dict] = []

    async def call_tool(_name, args):
        called.append(args)
        return {"ok": True, "data": {"order_id": args.get("order_id"), "status": "shipped"}}

    monkeypatch.setattr(orchestrator.mcp_client, "call_tool", call_tool)
    async def answer(_messages):
        yield "订单 O20261001001 已发货。"
    monkeypatch.setattr(orchestrator.llm_client, "chat_stream", answer)

    _ = [event async for event in orchestrator.handle_chat(str(session_id), "我买了什么", "multi")]
    # Simulate the first assistant turn identifying the order, as the model would.
    with test_db() as db:
        db.add(Message(session_id=session_id, role="assistant", content="你购买的订单是 O20261001001。"))
        db.commit()
    events = [event async for event in orchestrator.handle_chat(str(session_id), "那它什么时候到", "multi")]
    assert called[-1]["order_id"] == "O20261001001"
    assert any(b'"order_id": "O20261001001"' in event for event in events)


async def _intent_order(_messages):
    return "order"
