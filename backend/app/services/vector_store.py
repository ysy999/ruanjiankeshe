"""Milvus vector storage for knowledge base chunks."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

from app.config import settings

COLLECTION_NAME = "knowledge_chunks"


def _client():
    try:
        from pymilvus import MilvusClient
    except ImportError as exc:
        raise RuntimeError("Milvus support requires pymilvus. Install it with pip install pymilvus.") from exc
    return MilvusClient(uri=f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}")


def init_collection() -> None:
    """Create the knowledge collection and IVF_FLAT vector index if absent."""
    from pymilvus import DataType, MilvusClient

    client = _client()
    try:
        if client.has_collection(collection_name=COLLECTION_NAME):
            return
        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field(field_name="id", datatype=DataType.VARCHAR, is_primary=True, max_length=128)
        schema.add_field(field_name="chunk_text", datatype=DataType.VARCHAR, max_length=8192)
        schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=settings.EMBEDDING_DIM)
        schema.add_field(field_name="doc_name", datatype=DataType.VARCHAR, max_length=512)
        schema.add_field(field_name="version", datatype=DataType.VARCHAR, max_length=64)
        schema.add_field(field_name="page", datatype=DataType.INT64)
        schema.add_field(field_name="doc_type", datatype=DataType.VARCHAR, max_length=32)
        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type="IVF_FLAT",
            metric_type="L2",
            params={"nlist": 128},
        )
        client.create_collection(
            collection_name=COLLECTION_NAME,
            schema=schema,
            index_params=index_params,
        )
    finally:
        client.close()


def _stable_id(doc_name: str, version: str, chunk: dict[str, Any], index: int) -> str:
    identity = f"{doc_name}\0{version}\0{chunk.get('page') or 0}\0{chunk.get('chunk_index', index)}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def upsert_chunks(
    chunks: list[dict], embeddings: list[list[float]], doc_name: str, version: str
) -> None:
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must have the same length")
    if any(len(vector) != settings.EMBEDDING_DIM for vector in embeddings):
        raise ValueError(f"All vectors must have dimension {settings.EMBEDDING_DIM}")
    init_collection()
    rows = []
    for index, (chunk, vector) in enumerate(zip(chunks, embeddings, strict=True)):
        rows.append({
            "id": _stable_id(doc_name, version, chunk, index),
            "chunk_text": str(chunk.get("text", chunk.get("chunk_text", "")))[:8192],
            "vector": vector,
            "doc_name": doc_name[:512],
            "version": version[:64],
            "page": int(chunk.get("page") or 0),
            "doc_type": str(chunk.get("doc_type", Path(doc_name).suffix.lstrip(".")))[:32],
        })
    if rows:
        client = _client()
        try:
            client.upsert(collection_name=COLLECTION_NAME, data=rows)
            client.flush(collection_name=COLLECTION_NAME)
        finally:
            client.close()


def search(
    query_vec: list[float], top_k: int = 5, doc_type: str | None = None
) -> list[dict]:
    if len(query_vec) != settings.EMBEDDING_DIM:
        raise ValueError(f"query vector must have dimension {settings.EMBEDDING_DIM}")
    if top_k <= 0:
        return []
    client = _client()
    try:
        if not client.has_collection(collection_name=COLLECTION_NAME):
            return []
        client.load_collection(collection_name=COLLECTION_NAME)
        expr = 'version != "deprecated"'
        if doc_type:
            escaped_type = doc_type.replace('"', '\\"')
            expr += f' and doc_type == "{escaped_type}"'
        result = client.search(
            collection_name=COLLECTION_NAME,
            data=[query_vec],
            anns_field="vector",
            search_params={"metric_type": "L2", "params": {"nprobe": 16}},
            limit=top_k,
            filter=expr,
            output_fields=["chunk_text", "doc_name", "page"],
        )
        hits = result[0] if result else []
        output = [
            {
                "chunk_text": hit.get("entity", {}).get("chunk_text", ""),
                "doc_name": hit.get("entity", {}).get("doc_name", ""),
                "score": float(hit.get("distance", 0.0)),
                "page": int(hit.get("entity", {}).get("page", 0)) or None,
            }
            for hit in hits
        ]
        output.sort(key=lambda item: item["score"])
        return output
    finally:
        client.close()


def mark_deprecated(doc_name: str, old_version: str) -> None:
    client = _client()
    try:
        if not client.has_collection(collection_name=COLLECTION_NAME):
            return
        rows = client.query(
            collection_name=COLLECTION_NAME,
            filter=f'doc_name == "{doc_name.replace(chr(34), chr(92) + chr(34))}" and version == "{old_version.replace(chr(34), chr(92) + chr(34))}"',
            output_fields=["id", "chunk_text", "vector", "doc_name", "version", "page", "doc_type"],
        )
        for row in rows:
            row["version"] = "deprecated"
        if rows:
            client.upsert(collection_name=COLLECTION_NAME, data=rows)
            client.flush(collection_name=COLLECTION_NAME)
    finally:
        client.close()


if __name__ == "__main__":
    from app.services.embedding_client import EmbeddingClient

    sample_chunks = [
        {"text": "订单付款后通常会在一个工作日内发货。", "page": 1, "chunk_index": 0, "doc_type": "txt"},
        {"text": "如需退货，请在签收后七天内提交申请。", "page": 2, "chunk_index": 1, "doc_type": "txt"},
        {"text": "物流信息可能需要发货后数小时才会更新。", "page": 3, "chunk_index": 2, "doc_type": "txt"},
    ]
    embedder = EmbeddingClient()
    vectors = embedder.embed_texts([chunk["text"] for chunk in sample_chunks])
    upsert_chunks(sample_chunks, vectors, "vector_store_sample.txt", "test-v1")
    results = search(embedder.embed_query("订单什么时候发货？"), top_k=3)
    print(f"检索到 {len(results)} 条：")
    for item in results:
        print(f"distance={item['score']:.4f} page={item['page']} {item['doc_name']}: {item['chunk_text']}")
