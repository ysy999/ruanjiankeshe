"""OpenAI-compatible remote embeddings for Alibaba Model Studio and Volcengine Ark."""

from __future__ import annotations

import math
import time
from typing import Any

from openai import OpenAI

from app.config import settings


class EmbeddingClient:
    MAX_ATTEMPTS = 3

    def __init__(self) -> None:
        self.provider = settings.EMBEDDING_PROVIDER.strip().lower()
        self.api_key = settings.EMBEDDING_API_KEY
        if not self.api_key and self.provider in {"dashscope", "aliyun", "qwen"}:
            self.api_key = settings.DASHSCOPE_API_KEY
        self.base_url = settings.EMBEDDING_BASE_URL.rstrip("/")
        if self.provider in {"dashscope", "aliyun", "qwen"} and self.base_url.endswith("/api/v1"):
            self.base_url = self.base_url[: -len("/api/v1")] + "/compatible-mode/v1"
        self.model = settings.EMBEDDING_MODEL
        self.dim = settings.EMBEDDING_DIM
        # Alibaba's text-embedding-v4 accepts up to 10 items per call. Ark accepts more;
        # 25 keeps batches small and works with common deployed endpoints.
        self.batch_size = 10 if self.provider in {"dashscope", "aliyun", "qwen"} else 25

    def _request(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            raise RuntimeError(
                "Embedding API key is missing. Set EMBEDDING_API_KEY in backend/.env "
                "(or DASHSCOPE_API_KEY when using Alibaba Model Studio)."
            )
        client = OpenAI(api_key=self.api_key, base_url=self.base_url.rstrip("/"), timeout=60.0)
        last_error: Exception | None = None
        for attempt in range(self.MAX_ATTEMPTS):
            try:
                request: dict[str, Any] = {
                    "model": self.model,
                    "input": texts,
                    "encoding_format": "float",
                }
                if self.provider in {"dashscope", "aliyun", "qwen"}:
                    request["dimensions"] = self.dim
                response = client.embeddings.create(**request)
                records = sorted(response.data, key=lambda record: record.index)
                vectors = [[float(value) for value in record.embedding] for record in records]
                if len(vectors) != len(texts):
                    raise RuntimeError(f"Expected {len(texts)} vectors, received {len(vectors)}")
                for vector in vectors:
                    if len(vector) != self.dim:
                        raise RuntimeError(
                            f"Configured embedding dimension is {self.dim}, "
                            f"but provider returned {len(vector)}. Match EMBEDDING_DIM to the model."
                        )
                return vectors
            except Exception as exc:
                last_error = exc
                if attempt + 1 < self.MAX_ATTEMPTS:
                    time.sleep(2**attempt)
        raise RuntimeError(f"Embedding request failed after {self.MAX_ATTEMPTS} attempts: {last_error}") from last_error

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed document texts in bounded serial batches with exponential retries."""
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            embeddings.extend(self._request(texts[start : start + self.batch_size]))
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        """Embed a single search query using the configured remote embedding model."""
        return self._request([text])[0]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm_left = math.sqrt(sum(value * value for value in left))
    norm_right = math.sqrt(sum(value * value for value in right))
    return dot / (norm_left * norm_right) if norm_left and norm_right else 0.0


if __name__ == "__main__":
    client = EmbeddingClient()
    sentences = ["订单通常会在付款后尽快安排发货。", "支付完成后，商家一般会尽早寄出商品。"]
    vectors = client.embed_texts(sentences)
    print(f"向量维度：{len(vectors[0])}")
    print(f"余弦相似度：{_cosine_similarity(vectors[0], vectors[1]):.6f}")
