from pathlib import Path

from app.services import embedding_client, ingest_pipeline, vector_store
from app.services.knowledge_watcher import source_files


def test_ingest_indexes_temporary_markdown(tmp_path: Path, test_db, monkeypatch):
    source = tmp_path / "refund.md"
    source.write_text(
        "退款政策\n\n" + "消费者可在签收后七天内申请无理由退款，请通过订单详情提交申请。\n\n" * 5,
        encoding="utf-8",
    )
    normalized_path = str(source.resolve())
    with test_db() as db:
        db.execute(source_files.insert().values(path=normalized_path, md5="a" * 32, status="pending"))
        db.commit()

    fake_vectors: dict[str, list[dict]] = {}
    monkeypatch.setattr(embedding_client.EmbeddingClient, "embed_texts", lambda _self, texts: [[float(len(text))] for text in texts])
    monkeypatch.setattr(ingest_pipeline.settings, "EMBEDDING_DIM", 1, raising=False)
    monkeypatch.setattr(vector_store.settings, "EMBEDDING_DIM", 1, raising=False)
    monkeypatch.setattr(vector_store, "upsert_chunks", lambda chunks, _vectors, name, version: fake_vectors.update({name: [{"chunk_text": c["text"], "doc_name": name, "version": version} for c in chunks]}))
    monkeypatch.setattr(vector_store, "mark_deprecated", lambda *_args: None)
    result = ingest_pipeline.ingest(normalized_path)
    found = [item for item in fake_vectors[result["doc_name"]] if "七天" in item["chunk_text"]]
    assert result["chunk_count"] > 0
    assert found
