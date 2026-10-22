"""逻辑链：从已采纳正文里把「因为 → 所以 → 但是」摆出来。

**纯规则、不调用模型。** 这是把正文里**已有的**结构摆出来，不是判断它讲不
讲得通 —— 后者是逻辑自检（LLM 层）的事。链是材料，问题是判断，两者在界面
上并列但绝不混在一起。

规则识别连接词，不理解句子。误报的代价只是多列一句；它**不接入任何自动
检查**，所以不因此收紧规则。
"""

from __future__ import annotations

import re

KIND_LABELS: dict[str, str] = {
    "cause": "因果",
    "turn": "转折",
    "reveal": "揭示",
}

# 按这个顺序匹配：一句同时命中多类时取第一个。因果优先于转折，因为
# 「因为…但是…」里作者真正想推进的是因果。
_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("cause", ("因为", "由于", "所以", "于是", "因此", "结果", "于是乎")),
    ("turn", ("但是", "然而", "可是", "却", "不料", "谁知", "偏偏")),
    ("reveal", ("原来", "才发现", "竟是", "终于明白", "这才知道")),
)

_PARA_SPLIT = re.compile(r"\n\s*\n")
# 句末标点：中英文句号、问号、叹号、省略号。分号不算 —— 它连的是同一个
# 句子的两半，切开会让「因为…；所以…」断成两句。
_SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?…])")


def _split_sentences(paragraph: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_SPLIT.split(paragraph) if part.strip()]


def _match(sentence: str) -> tuple[str, str] | None:
    for kind, markers in _MARKERS:
        for marker in markers:
            if marker in sentence:
                return kind, marker
    return None


def extract_chain(text: str | None) -> list[dict]:
    """按原文顺序返回命中的句子；一段都没命中时返回空列表（不硬凑）。"""
    if not text:
        return []
    chain: list[dict] = []
    # 段落序号按**非空段落**计数：作者数的是他看得见的段，空行不占位。
    index = 0
    for paragraph in _PARA_SPLIT.split(text):
        body = paragraph.strip()
        if not body:
            continue
        index += 1
        for sentence in _split_sentences(body):
            hit = _match(sentence)
            if hit is None:
                continue
            kind, marker = hit
            chain.append(
                {
                    "paragraph": index,
                    "sentence": sentence,
                    "kind": kind,
                    "kind_label": KIND_LABELS[kind],
                    "marker": marker,
                }
            )
    return chain


def summarize(chain: list[dict]) -> dict:
    counts = {key: 0 for key in KIND_LABELS}
    for item in chain:
        counts[item["kind"]] += 1
    return {"total": len(chain), **counts}
