import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from openai import APITimeoutError, PermissionDeniedError
from sqlalchemy import select

from app.db import SessionLocal
from app.models import CallLog, Message, Session as ChatSession, User
from app.service.profile_service import get_profile
from app.services import llm_client, mcp_client, rag_service
from app.services.memory_service import recall, remember_turn

logger = logging.getLogger(__name__)


def _record_chat_metrics(session_id: str, retrieve_ms: int, llm_ms: int, total_ms: int, success: bool) -> None:
    try:
        with SessionLocal() as db:
            db.add(CallLog(
                session_id=int(session_id) if session_id.isdigit() else None,
                tool_name="chat_metrics",
                params={"retrieve_ms": retrieve_ms, "llm_ms": llm_ms},
                result={"success": success},
                latency_ms=total_ms,
            ))
            db.commit()
    except Exception:
        logger.exception("Failed to persist chat metrics")


def _event(event: str, data: Any) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


def _order_args(message: str, history: list[dict[str, str]] | None = None) -> dict[str, str]:
    import re

    search_text = "\n".join([message, *(item.get("content", "") for item in (history or []))])
    order_id = re.search(r"\bO\d{11}\b", search_text, re.IGNORECASE)
    tracking_no = re.search(r"\b[A-Z0-9-]{8,30}\b", search_text, re.IGNORECASE)
    return {"order_id": order_id.group(0)} if order_id else (
        {"tracking_no": tracking_no.group(0)} if tracking_no else {}
    )


async def handle_chat(session_id: str, message: str, visitor_id: str) -> AsyncIterator[bytes]:
    total_started = time.perf_counter()
    retrieve_ms = 0
    llm_ms = 0
    metrics_recorded = False
    answer_parts: list[str] = []
    citations: list[dict[str, Any]] = []
    try:
        memories: list[str] = []
        try:
            memories = await recall(visitor_id, message)
        except Exception:
            logger.exception("用户长期记忆召回失败")

        assistant_message_id: int | None = None
        with SessionLocal() as db:
            session = db.scalar(select(ChatSession).where(ChatSession.id == int(session_id)))
            if session is None:
                yield _event("error", {"message": "session not found"})
                return
            owner = db.get(User, session.user_id)
            if owner is None or owner.username != f"visitor-{visitor_id}":
                yield _event("error", {"message": "session not found"})
                return
            history_rows = db.scalars(
                select(Message).where(Message.session_id == session.id)
                .order_by(Message.created_at.desc(), Message.id.desc()).limit(10)
            ).all()
            history = [{"role": row.role, "content": row.content} for row in reversed(history_rows)]
            db.add(Message(session_id=session.id, role="user", content=message))
            if not session.title or session.title == "新对话":
                session.title = message[:20]
            db.commit()
            profile = get_profile(visitor_id)

        retrieve_started = time.perf_counter()
        intent_prompt = "判断用户问题属于 knowledge / order / chitchat 三类中的哪一类，只返回一个词"
        try:
            intent = await llm_client.classify_intent([
                {"role": "system", "content": intent_prompt},
                {"role": "user", "content": message},
            ])
        except Exception:
            logger.exception("意图分类调用失败")
            intent = "chitchat"

        context = ""
        retrieval_empty = False
        order_lookup_failed = False
        if intent == "knowledge":
            try:
                chunks = await rag_service.retrieve(message)
                citations = [
                    {"doc_name": str(chunk.get("doc_name", "")), "snippet": str(chunk.get("snippet", chunk.get("content", "")))}
                    for chunk in chunks
                ]
                context = "\n\n参考资料：\n" + "\n".join(
                    f"[{item['doc_name']}] {item['snippet']}" for item in citations
                ) if citations else ""
                retrieval_empty = not bool(chunks)
            except Exception:
                logger.exception("RAG 检索失败")
                retrieval_empty = True
        elif intent == "order":
            try:
                args = _order_args(message, history)
                tool = "get_order_status" if "order_id" in args else "get_logistics"
                result = await mcp_client.call_tool(tool, args)
                if result.get("ok") is False:
                    order_lookup_failed = True
                    detail = result.get("error", "未知错误")
                    context = (
                        "\n\n订单工具查询失败。请用自然、简短的语言告知用户："
                        f"订单系统暂时查询失败。内部错误信息：{detail}"
                    )
                else:
                    context = f"\n\n订单工具查询结果：{json.dumps(result, ensure_ascii=False, default=str)}"
            except Exception:
                logger.exception("订单工具调用失败")
                order_lookup_failed = True
                context = "\n\n订单工具调用异常，请用自然语言告知用户订单系统暂时查询失败。"
        retrieve_ms = int((time.perf_counter() - retrieve_started) * 1000)

        style = profile.get("style", "friendly")
        length = profile.get("length", "medium")
        nickname = profile.get("nickname", "")
        system = (
            f"你是一个专业的智能客服。回复风格：{style}；回复长度：{length}。"
            + (f"称呼用户为{nickname}。" if nickname else "")
            + ("\n没有检索到相关资料，请直接告诉用户暂未找到答案并建议转人工。" if retrieval_empty else "")
            + (f"\n{context}" if context else "")
            + ("\n【用户长期记忆】：" + "；".join(memories) if memories else "")
        )
        model_messages = [{"role": "system", "content": system}, *history, {"role": "user", "content": message}]
        llm_started = time.perf_counter()
        try:
            async for delta in llm_client.chat_stream(model_messages):
                answer_parts.append(delta)
                yield _event("delta", {"delta": delta})
        except Exception as exc:
            llm_ms = int((time.perf_counter() - llm_started) * 1000)
            logger.exception("LLM 流式生成失败")
            _record_chat_metrics(session_id, retrieve_ms, llm_ms, int((time.perf_counter() - total_started) * 1000), False)
            metrics_recorded = True
            if isinstance(exc, PermissionDeniedError):
                yield _event("error", {
                    "code": 403,
                    "msg": "模型服务拒绝了请求。请确认 backend/.env 中的 API Key、模型名称和账户额度正确。",
                })
            elif isinstance(exc, (APITimeoutError, TimeoutError)):
                yield _event("error", {"code": 504, "msg": "模型响应超时"})
            else:
                yield _event("error", {"code": 500, "msg": "模型调用失败，请检查模型配置和服务状态。"})
            return
        llm_ms = int((time.perf_counter() - llm_started) * 1000)

        if citations and profile.get("show_sources", True):
            yield _event("citations", citations)
        full_answer = "".join(answer_parts)
        with SessionLocal() as db:
            session = db.get(ChatSession, int(session_id))
            if session is not None:
                assistant_message = Message(
                    session_id=session.id,
                    role="assistant",
                    content=full_answer,
                    citations=citations or None,
                )
                db.add(assistant_message)
                db.commit()
                db.refresh(assistant_message)
                assistant_message_id = assistant_message.id
        try:
            await remember_turn(visitor_id, message, full_answer)
        except Exception:
            logger.exception("用户长期记忆写入失败")
        _record_chat_metrics(session_id, retrieve_ms, llm_ms, int((time.perf_counter() - total_started) * 1000), True)
        metrics_recorded = True
        yield _event("done", {"status": "ok", "message_id": assistant_message_id})
    except Exception:
        logger.exception("聊天编排失败")
        if not metrics_recorded:
            _record_chat_metrics(session_id, retrieve_ms, llm_ms, int((time.perf_counter() - total_started) * 1000), False)
        yield _event("error", {"message": "处理消息时发生错误"})
