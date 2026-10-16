"""世界观条目的类型与硬度词表，以及把模型产出归一化到词表的函数。

这里是唯一真相：接口下发给前端、归一化函数、角色卡契约三处都用它。
多一份就会漂移 —— 与 SLOT_REGISTRY 同一条教训。
"""

from __future__ import annotations

ENTRY_TYPES: dict[str, str] = {
    "place": "地理",
    "faction": "势力",
    "organization": "组织",
    "rule": "规则体系",
    "event": "历史事件",
    "item": "物品",
    "concept": "概念",
    "term": "术语",
}

HARDNESS_LEVELS: dict[str, str] = {
    "hard": "硬规则",
    "soft": "软规则",
    "atmosphere": "氛围",
}

_TYPE_BY_LABEL = {label: key for key, label in ENTRY_TYPES.items()}
_HARDNESS_BY_LABEL = {label: key for key, label in HARDNESS_LEVELS.items()}


def normalize_type(value: str) -> str:
    """中文名与英文键都归到同一个 key；未知值报错。

    报错而不是猜一个类型：猜错会把一条设定塞进错误的分类，而作者可能
    在很远之后才发现。报错只影响这一行，不拖垮整批候选。
    """
    key = (value or "").strip()
    if key in ENTRY_TYPES:
        return key
    if key in _TYPE_BY_LABEL:
        return _TYPE_BY_LABEL[key]
    raise ValueError(
        f"未知的设定类型「{value}」，可用值：{'、'.join(ENTRY_TYPES.values())}"
    )


def normalize_hardness(value: str | None) -> str | None:
    """只在规则类条目上保留硬度；非法值与空值一律归为 None。

    不报错：模型对非规则条目填了硬度、或填了「很硬」这类描述，都不该
    让一条本来可用的候选被拒。
    """
    key = (value or "").strip()
    if key in HARDNESS_LEVELS:
        return key
    if key in _HARDNESS_BY_LABEL:
        return _HARDNESS_BY_LABEL[key]
    return None
