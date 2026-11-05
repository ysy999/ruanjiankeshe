from typing import Any

from fastapi import APIRouter, Query

from app.services.mcp_client import mcp_client

router = APIRouter(prefix="/test/mcp", tags=["mcp-test"])


@router.get("")
async def test_mcp(
    order_id: str = Query(..., pattern=r"^O\d+$"),
    tracking_no: str | None = None,
) -> dict[str, Any]:
    status = await mcp_client.call_tool("get_order_status", {"order_id": order_id})
    logistics = await mcp_client.call_tool(
        "get_logistics",
        {"order_id": order_id, **({"tracking_no": tracking_no} if tracking_no else {})},
    )
    return {"code": 0, "msg": "ok", "data": {"order_status": status, "logistics": logistics}}
