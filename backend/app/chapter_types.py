"""章节结构的状态词表与校验。

P1c-1 只允许「规划中 / 已确认」；P2 写正文时扩展 written，P4 扩展伏笔闭环
状态。扩展时必须同步服务层校验与前端下拉 —— 与 ENTRY_TYPES 的教训一致。
"""

from __future__ import annotations

STATUS_VALUES: tuple[str, ...] = ("planned", "confirmed")
STATUS_LABELS: dict[str, str] = {
    "planned": "规划中",
    "confirmed": "已确认",
}


def normalize_status(value: str | None, *, default: str = "planned") -> str:
    key = (value or "").strip() or default
    if key not in STATUS_VALUES:
        raise ValueError(f"未知的章节状态「{value}」，可用值：planned / confirmed")
    return key
