"""一致性审计的分类词表与归一化。

三张词表在这里定义一次，规则层、LLM 层、API 序列化与前端都从这里投影 ——
沿用 `world_types` 的先例：词表只留一份，避免各层各抄一份、漂移了没人发现。
"""

from __future__ import annotations

from typing import Any

AUDIT_KINDS = {
    "repetition": "重复",
    "alias": "称呼",
    "setting": "设定",
    "character": "人物",
    "timeline": "时间线",
    "term": "术语",
    "other": "其他",
}

AUDIT_SEVERITIES = {
    "critical": "致命",
    "major": "严重",
    "minor": "提示",
}

AUDIT_SOURCES = {"rule": "规则", "llm": "LLM"}

DEFAULT_KIND = "other"
DEFAULT_SEVERITY = "minor"

# 作者的四种处理动作。这是显式选择，未知值必须报错而不是猜一档。
_RESOLUTIONS = frozenset({"story", "setting", "character", "exception"})

_KINDS_BY_LABEL = {label: key for key, label in AUDIT_KINDS.items()}
_SEVERITIES_BY_LABEL = {label: key for key, label in AUDIT_SEVERITIES.items()}


def _clean(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def normalize_kind(value: Any) -> str:
    """接受英文键或中文标签；未知值归 `other`，不抛错。"""
    text = _clean(value)
    if text in AUDIT_KINDS:
        return text
    return _KINDS_BY_LABEL.get(text, DEFAULT_KIND)


def normalize_severity(value: Any) -> str:
    """接受英文键或中文标签；未知值归 `minor`，不抛错。"""
    text = _clean(value)
    if text in AUDIT_SEVERITIES:
        return text
    return _SEVERITIES_BY_LABEL.get(text, DEFAULT_SEVERITY)


def normalize_resolution(value: Any) -> str:
    """只接受四种作者处理方式，其余抛 `ValueError`。

    与 kind / severity 不同 —— 那是模型产出的归类，猜错一档的代价小；
    处理方式是作者点下的显式动作，静默归到某一档会伪造作者的意图。
    """
    text = _clean(value)
    if text in _RESOLUTIONS:
        return text
    raise ValueError(
        f"不支持的处理方式：{value!r}（只接受 story / setting / character / exception）"
    )
