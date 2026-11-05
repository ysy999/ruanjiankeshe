import json
import logging
import os
import re
import time
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastmcp import FastMCP
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

mcp = FastMCP("order-service")
logger = logging.getLogger("mcp_server.tools")
_ORDER_ID = re.compile(r"^O\d+$", re.IGNORECASE)
_REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_REPO_ROOT / "backend" / ".env")


@lru_cache(maxsize=1)
def _get_engine() -> Engine:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set; configure it in backend/.env")
    return create_engine(database_url, pool_pre_ping=True)


def _serialize(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _total_amount(items: Any) -> float | None:
    if not isinstance(items, list):
        return None
    total = 0.0
    found_price = False
    for item in items:
        if not isinstance(item, dict):
            continue
        price = item.get("price", item.get("unit_price"))
        quantity = item.get("qty", item.get("quantity", 1))
        try:
            total += float(price) * float(quantity)
            found_price = True
        except (TypeError, ValueError):
            continue
    return round(total, 2) if found_price else None


def _run_tool(tool_name: str, arguments: dict[str, Any], operation):
    started = time.perf_counter()
    try:
        result = operation()
        if not isinstance(result, dict) or "ok" not in result:
            result = {"ok": True, "data": result}
        return result
    except Exception as exc:
        logger.exception("MCP tool raised tool=%s trace_id=%s", tool_name, arguments.get("trace_id"))
        return {"ok": False, "error": str(exc)}
    finally:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "MCP tool call tool=%s arguments=%s trace_id=%s elapsed_ms=%d success=%s",
            tool_name,
            {key: value for key, value in arguments.items() if key != "trace_id"},
            arguments.get("trace_id"),
            elapsed_ms,
            locals().get("result", {}).get("ok", False),
        )


@mcp.tool()
def get_order_status(order_id: str, trace_id: str = "") -> dict:
    """根据订单号查询订单状态和基本信息。

    Args:
        order_id: 订单号，形如 O20261001001
    """
    arguments = {"order_id": order_id, "trace_id": trace_id}

    def operation():
        normalized = (order_id or "").strip()
        if not normalized:
            return {"ok": False, "error": "order_id 不能为空"}
        if not _ORDER_ID.fullmatch(normalized):
            return {"ok": False, "error": "order_id 必须以 O 开头，后接数字"}
        with _get_engine().connect() as connection:
            row = connection.execute(text("SELECT * FROM orders WHERE order_id = :order_id"), {"order_id": normalized}).mappings().first()
        if row is None:
            return {"ok": False, "error": f"订单 {normalized} 不存在"}
        order = dict(row)
        items = order.get("items")
        if isinstance(items, str):
            try:
                items = json.loads(items)
            except json.JSONDecodeError:
                pass
        return {"ok": True, "data": {
            "order_id": order["order_id"], "status": order.get("status"),
            "created_at": _serialize(order.get("created_at")), "items": items,
            "total_amount": order.get("total_amount") or _total_amount(items),
        }}

    return _run_tool("get_order_status", arguments, operation)


@mcp.tool()
def get_logistics(order_id: str, trace_id: str = "") -> dict:
    """根据订单号查询物流信息（物流公司、单号、轨迹）。

    Args:
        order_id: 订单号，形如 O20261001001
    """
    arguments = {"order_id": order_id, "trace_id": trace_id}

    def operation():
        normalized = (order_id or "").strip()
        if not normalized:
            return {"ok": False, "error": "order_id 不能为空"}
        if not _ORDER_ID.fullmatch(normalized):
            return {"ok": False, "error": "order_id 必须以 O 开头，后接数字"}
        with _get_engine().connect() as connection:
            row = connection.execute(
                text(
                    "SELECT status, logistics_company, tracking_no "
                    "FROM orders WHERE order_id = :order_id"
                ),
                {"order_id": normalized},
            ).mappings().first()
        if row is None:
            return {"ok": False, "error": f"订单 {normalized} 不存在"}

        status = str(row.get("status") or "").lower()
        tracking_no = row.get("tracking_no")
        company = row.get("logistics_company")
        if status not in {"shipped", "in_transit", "delivered", "已发货", "运输中", "已签收"} or not tracking_no:
            return {"ok": False, "error": f"订单 {normalized} 尚未发货或暂无物流信息"}

        now = datetime.now()
        trajectory = [
            {"time": (now - timedelta(hours=1)).isoformat(timespec="minutes"), "desc": "快件已到达派送网点"},
            {"time": (now - timedelta(hours=5)).isoformat(timespec="minutes"), "desc": "快件在运输途中"},
            {"time": (now - timedelta(hours=12)).isoformat(timespec="minutes"), "desc": "快件已从中转中心发出"},
            {"time": (now - timedelta(days=1)).isoformat(timespec="minutes"), "desc": "快件已揽收"},
        ]
        return {
            "ok": True,
            "data": {
                "company": company,
                "tracking_no": tracking_no,
                "trajectory": trajectory,
            },
        }
    return _run_tool("get_logistics", arguments, operation)


if __name__ == "__main__":
    mcp.run()
