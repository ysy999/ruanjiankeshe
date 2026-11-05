"""Load Markdown, text and PDF files and split them into overlapping chunks."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

TARGET_CHUNK_SIZE = 400
CHUNK_OVERLAP = 50

_SPECIAL_RUN = re.compile(r"([~`!@#$%^&*_=+|\\<>/\-])\1{4,}")
_PAGE_NUMBER = re.compile(r"^\s*(?:page\s*)?\d+(?:\s*(?:of|/)\s*\d+)?\s*$", re.IGNORECASE)
_SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？.!?；;])\s*")


def _clean_text(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[\t\u00a0 ]+", " ", line).strip() for line in text.split("\n")]

    # Drop frequent PDF header/footer lines and isolated page numbers.
    counts: dict[str, int] = {}
    for line in lines:
        if line:
            counts[line] = counts.get(line, 0) + 1
    repeated = {line for line, count in counts.items() if count >= 3 and len(line) <= 120}
    cleaned: list[str] = []
    for line in lines:
        if not line or _PAGE_NUMBER.fullmatch(line) or line in repeated:
            cleaned.append("")
            continue
        cleaned.append(_SPECIAL_RUN.sub("", line))

    paragraphs: list[str] = []
    for line in cleaned:
        if line:
            paragraphs.append(line)
        elif paragraphs and paragraphs[-1] != "":
            paragraphs.append("")
    return "\n".join(paragraphs).strip()


def _split_long_paragraph(paragraph: str, limit: int) -> list[str]:
    if len(paragraph) <= limit:
        return [paragraph]
    sentences = [part.strip() for part in _SENTENCE_BOUNDARY.split(paragraph) if part.strip()]
    if len(sentences) <= 1:
        return [paragraph[i : i + limit] for i in range(0, len(paragraph), limit)]
    result: list[str] = []
    current = ""
    for sentence in sentences:
        while len(sentence) > limit:
            if current:
                result.append(current)
                current = ""
            result.append(sentence[:limit])
            sentence = sentence[limit:]
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > limit:
            result.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        result.append(current)
    return result


def _make_chunks(text: str, source_doc: str, page: int | None) -> list[dict[str, Any]]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    units: list[str] = []
    for paragraph in paragraphs:
        units.extend(_split_long_paragraph(paragraph, TARGET_CHUNK_SIZE))
    if not units:
        return []

    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n\n{unit}".strip() if current else unit
        if current and len(candidate) > TARGET_CHUNK_SIZE:
            chunks.append(current)
            overlap = current[-CHUNK_OVERLAP:]
            current = f"{overlap}\n\n{unit}".strip()
            # A long overlap can leave no room for the next paragraph; keep size bounded.
            if len(current) > TARGET_CHUNK_SIZE:
                current = current[-TARGET_CHUNK_SIZE:]
        else:
            current = candidate
    if current:
        chunks.append(current)

    return [
        {"text": chunk, "source_doc": source_doc, "page": page, "chunk_index": index}
        for index, chunk in enumerate(chunks)
    ]


def load_document(path: str) -> list[dict]:
    """Load a supported file and return text chunks with source and page metadata."""
    document_path = Path(path)
    extension = document_path.suffix.lower()
    if extension not in {".md", ".txt", ".pdf"}:
        raise ValueError(f"Unsupported document format: {extension or '(no extension)'}")
    if not document_path.is_file():
        raise FileNotFoundError(path)

    results: list[dict[str, Any]] = []
    if extension == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF support requires pypdf. Install it with pip install pypdf.") from exc
        reader = PdfReader(str(document_path))
        for page_number, page in enumerate(reader.pages, start=1):
            text = _clean_text(page.extract_text() or "")
            results.extend(_make_chunks(text, document_path.name, page_number))
    else:
        text = _clean_text(document_path.read_text(encoding="utf-8-sig"))
        results.extend(_make_chunks(text, document_path.name, None))
    return results


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sample_path = sys.argv[1]
    else:
        sample_path = Path(__file__).with_name("chunker_sample.txt")
        if not sample_path.exists():
            sample_path.write_text(
                "客服知识库示例\n\n" + "退货申请需要在订单签收后七天内提交。请提供订单编号并保持商品包装完整。\n\n" * 12,
                encoding="utf-8",
            )
    loaded = load_document(str(sample_path))
    print(f"文件：{sample_path}，共生成 {len(loaded)} 个 chunk")
    for chunk in loaded:
        print(f"[{chunk['chunk_index']}] page={chunk['page']} length={len(chunk['text'])}")
        print(chunk["text"][:120].replace("\n", " ") + ("…" if len(chunk["text"]) > 120 else ""))
