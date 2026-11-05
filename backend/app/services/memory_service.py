"""In-process Mem0 memory for visitor-specific long-term conversation facts."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)
_memory: Any = None


def _get_memory() -> Any:
    global _memory
    if _memory is None:
        try:
            from mem0 import Memory
        except ImportError as exc:
            raise RuntimeError("Mem0 is required. Install it with pip install mem0ai") from exc
        _memory = Memory.from_config(
            {
                "version": "v1.1",
                "embedder": {
                    "provider": "huggingface",
                    "config": {"model": "sentence-transformers/all-MiniLM-L6-v2"},
                },
                "vector_store": {
                    "provider": "memory",
                    "config": {"collection_name": "visitor_memories", "embedding_model_dims": 384},
                },
            }
        )
    return _memory


def _remember(visitor_id: str, user_msg: str, ai_msg: str) -> Any:
    return _get_memory().add(
        [
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": ai_msg},
        ],
        user_id=visitor_id,
    )


async def remember_turn(visitor_id: str, user_msg: str, ai_msg: str) -> None:
    """Store one completed user/assistant exchange."""
    await asyncio.to_thread(_remember, visitor_id, user_msg, ai_msg)


def _recall(visitor_id: str, query: str) -> list[str]:
    result = _get_memory().search(query, user_id=visitor_id, limit=3)
    if isinstance(result, dict):
        entries = result.get("results", [])
    else:
        entries = result or []
    memories = []
    for item in entries:
        if isinstance(item, dict):
            text = item.get("memory") or item.get("text")
        else:
            text = getattr(item, "memory", None) or getattr(item, "text", None)
        if isinstance(text, str) and text.strip():
            memories.append(text.strip())
    return memories[:3]


async def recall(visitor_id: str, query: str) -> list[str]:
    """Return up to three relevant memories for a visitor."""
    return await asyncio.to_thread(_recall, visitor_id, query)
