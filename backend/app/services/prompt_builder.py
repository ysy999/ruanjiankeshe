"""Build OpenAI-style messages for grounded e-commerce after-sales chat."""

from __future__ import annotations

from typing import Any


_STYLE_GUIDANCE = {
    "formal": "使用正式、礼貌、专业的表达。",
    "friendly": "使用友好、自然、易懂的表达。",
    "concise": "表达简洁，优先给出结论和必要步骤。",
}

_LENGTH_GUIDANCE = {
    "short": "回答控制在约 100 字以内。",
    "medium": "回答控制在约 200 字以内。",
    "long": "回答可详细说明，控制在约 500 字以内。",
}


def build_messages(
    user_query: str,
    history: list[dict],
    chunks: list[dict],
    profile: dict,
) -> list[dict[str, str]]:
    """Build a grounded chat prompt with recent conversation and optional citations."""
    style = str(profile.get("style", "friendly")).lower()
    length = str(profile.get("length", "medium")).lower()
    nickname = str(profile.get("nickname", "")).strip()

    system_parts = [
        "角色：你是电商售后领域的智能客服助手。",
        "规则：只能根据下面【参考资料】回答；资料里没有就明确说「根据现有资料我无法确定，建议联系人工客服」，不要编造。",
        f"语气偏好：{_STYLE_GUIDANCE.get(style, _STYLE_GUIDANCE['friendly'])}",
        f"长度偏好：{_LENGTH_GUIDANCE.get(length, _LENGTH_GUIDANCE['medium'])}",
    ]
    if nickname:
        system_parts.append(f"称呼用户为“{nickname}”。")
    system = "\n".join(system_parts)

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for item in history[-10:]:
        role = item.get("role")
        content = item.get("content")
        if role in {"system", "user", "assistant"} and isinstance(content, str):
            messages.append({"role": role, "content": content})

    if chunks:
        references = ["【参考资料】"]
        for index, chunk in enumerate(chunks, start=1):
            text = str(chunk.get("chunk_text", chunk.get("text", ""))).strip()
            references.append(f"[{index}] {text}")
        references.append("回答时用 [1][2] 标注引用来源。")
        messages.append({"role": "user", "content": "\n\n".join(references)})

    messages.append({"role": "user", "content": user_query})
    return messages


if __name__ == "__main__":
    sample = build_messages(
        user_query="商品签收后多久可以申请退货？",
        history=[
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好，请问有什么可以帮你？"},
        ],
        chunks=[
            {"chunk_text": "商品签收后七天内可提交退货申请。", "doc_name": "售后政策.md"},
            {"chunk_text": "申请时请保持商品及包装完好。", "doc_name": "售后政策.md"},
        ],
        profile={"style": "friendly", "length": "medium", "nickname": "小林"},
    )
    for message in sample:
        print(f"[{message['role']}]\n{message['content']}\n")
