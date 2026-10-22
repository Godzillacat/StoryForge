"""锁定目标的词表与归一化。

与 `ENTRY_TYPES` / `LOGIC_LAYERS` 同一条教训：词表只留一份，接口下发、
服务层校验、影响面分组与前端标签都从这里投影。
"""

from __future__ import annotations

from typing import Any

LOCK_TARGETS: dict[str, str] = {
    "architecture": "故事圣经",
    "entry": "设定条目",
    "volume": "卷",
    "chapter": "章",
    "scene": "场景",
}


def normalize_target_type(value: Any) -> str:
    """目标类型是作者显式指定的，未知值必须报错而不是回落。"""
    key = value.strip() if isinstance(value, str) else ""
    if key not in LOCK_TARGETS:
        raise ValueError(
            f"未知的锁定目标类型：{value!r}（可用值：{' / '.join(LOCK_TARGETS)}）"
        )
    return key
