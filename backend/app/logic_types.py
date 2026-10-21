"""逻辑自检的层面与时机词表。

与 `ENTRY_TYPES` 同一条教训：词表只留一份，契约、服务层归一化、
接口下发与前端标签都从这里投影。
"""

from __future__ import annotations

from typing import Any

LOGIC_LAYERS: dict[str, str] = {
    "world_rule": "世界规则",
    "causality": "因果链",
    "motivation": "动机与性格",
    "information": "信息流",
    "setting_load": "设定载荷",
    "other": "其他",
}

# 两个检查时机：正文开写前（场景卡 / 章纲）与定稿前（已采纳正文）。
LOGIC_STAGES: dict[str, str] = {
    "plan": "场景卡",
    "text": "正文",
}

DEFAULT_LAYER = "other"

_LAYERS_BY_LABEL = {label: key for key, label in LOGIC_LAYERS.items()}


def _clean(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def normalize_layer(value: Any) -> str:
    """接受英文键或中文标签；未知层归 `other`，不抛错。"""
    text = _clean(value)
    if text in LOGIC_LAYERS:
        return text
    return _LAYERS_BY_LABEL.get(text, DEFAULT_LAYER)


def normalize_stage(value: Any) -> str:
    """时机是作者显式选择，未知值必须报错。"""
    text = _clean(value)
    if text in LOGIC_STAGES:
        return text
    raise ValueError(
        f"未知的逻辑自检时机：{value!r}（只接受 plan / text）"
    )
