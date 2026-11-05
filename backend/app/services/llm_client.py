"""OpenAI-compatible online LLM client for Qwen and DeepSeek APIs."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Iterator
from typing import Any

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)
_END = object()


def _provider_base_url(provider: str, base_url: str) -> str:
    # Older project .env files used DashScope's native endpoint. The OpenAI client
    # needs the compatible-mode endpoint instead.
    value = base_url.rstrip("/")
    if provider in {"dashscope", "aliyun", "qwen"} and value.endswith("/api/v1"):
        return value[: -len("/api/v1")] + "/compatible-mode/v1"
    return value


def _client(api_key: str, base_url: str, timeout: float) -> OpenAI:
    if not api_key:
        raise RuntimeError(
            "LLM API key is missing. Set LLM_API_KEY in backend/.env "
            "(or DASHSCOPE_API_KEY when using DashScope)."
        )
    return OpenAI(api_key=api_key, base_url=base_url.rstrip("/"), timeout=timeout)


class LLMClient:
    def __init__(self, timeout: float = 60.0, retry_count: int = 2) -> None:
        self.provider = settings.LLM_PROVIDER.strip().lower()
        self.model = settings.LLM_MODEL
        self.base_url = _provider_base_url(self.provider, settings.LLM_BASE_URL)
        self.api_key = settings.LLM_API_KEY
        if not self.api_key and self.provider in {"dashscope", "aliyun", "qwen"}:
            self.api_key = settings.DASHSCOPE_API_KEY
        self.timeout = timeout
        self.retry_count = retry_count

    async def chat(self, messages: list[dict]) -> str:
        started = time.perf_counter()
        try:
            last_error: Exception | None = None
            for attempt in range(self.retry_count + 1):
                try:
                    def invoke() -> str:
                        response = _client(self.api_key, self.base_url, self.timeout).chat.completions.create(
                            model=self.model,
                            messages=messages,
                            stream=False,
                        )
                        content = response.choices[0].message.content
                        if isinstance(content, str):
                            return content
                        if content is None:
                            return ""
                        return "".join(
                            item.text for item in content
                            if getattr(item, "type", None) == "text" and getattr(item, "text", None)
                        )

                    return await asyncio.wait_for(asyncio.to_thread(invoke), timeout=self.timeout)
                except Exception as exc:
                    last_error = exc
                    if attempt >= self.retry_count:
                        raise
            raise RuntimeError("LLM request failed") from last_error
        finally:
            logger.info(
                "LLM chat provider=%s model=%s message_count=%d duration_ms=%d",
                self.provider,
                self.model,
                len(messages),
                int((time.perf_counter() - started) * 1000),
            )

    async def chat_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        started = time.perf_counter()
        try:
            client = _client(self.api_key, self.base_url, self.timeout)

            def open_stream() -> Iterator[Any]:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    stream=True,
                )
                return iter(response)

            iterator = await asyncio.wait_for(asyncio.to_thread(open_stream), timeout=self.timeout)

            def next_item() -> Any:
                return next(iterator, _END)

            while True:
                item = await asyncio.wait_for(asyncio.to_thread(next_item), timeout=self.timeout)
                if item is _END:
                    break
                if not item.choices:
                    continue
                delta = item.choices[0].delta.content
                if isinstance(delta, str) and delta:
                    yield delta
                elif isinstance(delta, list):
                    for part in delta:
                        text = getattr(part, "text", None)
                        if text:
                            yield text
        finally:
            logger.info(
                "LLM chat_stream provider=%s model=%s message_count=%d duration_ms=%d",
                self.provider,
                self.model,
                len(messages),
                int((time.perf_counter() - started) * 1000),
            )


llm_client = LLMClient()


async def classify_intent(messages: list[dict[str, str]]) -> str:
    try:
        result = (await llm_client.chat(messages)).strip().lower()
    except Exception:
        logger.exception("Intent classification failed")
        raise
    return result if result in {"knowledge", "order", "chitchat"} else "chitchat"


async def chat_stream(messages: list[dict[str, str]]) -> AsyncIterator[str]:
    async for delta in llm_client.chat_stream(messages):
        yield delta
