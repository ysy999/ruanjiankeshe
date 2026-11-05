import asyncio
import json
import logging
import re
import time
from uuid import uuid4
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from app.db import SessionLocal
from app.models import CallLog

logger = logging.getLogger(__name__)
_ORDER_ID_RE = re.compile(r"^O\d+$", re.IGNORECASE)


class MCPClient:
    def __init__(self) -> None:
        self._stack: AsyncExitStack | None = None
        self._session: Any = None

    async def connect(self) -> None:
        if self._session is not None:
            return
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        stack = AsyncExitStack()
        try:
            transport = await stack.enter_async_context(
                stdio_client(
                    StdioServerParameters(
                        command="python",
                        args=["-m", "mcp_server.main"],
                        cwd=str(Path(__file__).resolve().parents[3]),
                    )
                )
            )
            read_stream, write_stream = transport
            session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
            await session.initialize()
        except Exception:
            await stack.aclose()
            logger.exception("MCP server connection failed")
            raise
        self._stack = stack
        self._session = session

    async def close(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._session = None

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        trace_id = str(arguments.get("trace_id") or uuid4()) if isinstance(arguments, dict) else str(uuid4())
        call_arguments = {**arguments, "trace_id": trace_id} if isinstance(arguments, dict) else arguments
        result: dict[str, Any]
        try:
            if not isinstance(arguments, dict):
                raise ValueError("arguments must be an object")
            if name in {"get_order_status", "get_logistics"}:
                order_id = arguments.get("order_id")
                if not isinstance(order_id, str) or not _ORDER_ID_RE.fullmatch(order_id):
                    raise ValueError("order_id is required and must match O followed by digits")
            if self._session is None:
                raise RuntimeError("MCP client is not connected")
            raw = await asyncio.wait_for(
                self._session.call_tool(name, arguments=call_arguments), timeout=10
            )
            structured = getattr(raw, "structuredContent", None) or getattr(raw, "structured_content", None)
            if structured is not None:
                if isinstance(structured, dict) and isinstance(structured.get("ok"), bool):
                    result = structured
                else:
                    result = {"ok": not bool(getattr(raw, "isError", False)), "data": structured}
            else:
                content = []
                for item in getattr(raw, "content", []) or []:
                    text = getattr(item, "text", None)
                    content.append(text if text is not None else str(item))
                is_error = bool(getattr(raw, "isError", getattr(raw, "is_error", False)))
                result = {"ok": not is_error, "data": content}
                if is_error:
                    result["error"] = "; ".join(content) or "MCP tool returned an error"
        except asyncio.TimeoutError:
            result = {"ok": False, "error": "MCP tool call timed out after 10 seconds"}
        except Exception as exc:
            logger.exception("MCP tool call failed: %s", name)
            result = {"ok": False, "error": str(exc)}
        finally:
            latency_ms = int((time.perf_counter() - started) * 1000)
            try:
                with SessionLocal() as db:
                    session_id = arguments.get("session_id") if isinstance(arguments, dict) else None
                    db.add(CallLog(
                        session_id=int(session_id) if session_id is not None else None,
                        tool_name=name[:64],
                        params={**arguments, "trace_id": trace_id} if isinstance(arguments, dict) else {"value": str(arguments), "trace_id": trace_id},
                        result=result,
                        latency_ms=latency_ms,
                    ))
                    db.commit()
                logger.info(
                    "MCP client call tool=%s trace_id=%s elapsed_ms=%d success=%s",
                    name,
                    trace_id,
                    latency_ms,
                    result.get("ok", False),
                )
            except Exception:
                logger.exception("Failed to persist MCP call log")
        return result


mcp_client = MCPClient()


async def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Compatibility wrapper for the orchestrator."""
    return await mcp_client.call_tool(name, args)
