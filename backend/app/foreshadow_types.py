"""伏笔的生命周期状态。

**不复用 `chapter_types` 的词表**：章节的 `confirmed`（作者确认过规划）与
伏笔的 `paid`（已经在正文里兑现）是两种语义，共用一个值会让读者以为它们
是一回事。

状态与「在哪个场景」是两件事：位置是事实，状态是判断。作者说「这条我不
收了」，埋设位置还在，不该把它翻回 `planted` —— 见 `effective_status`。
"""

from __future__ import annotations

from typing import Any

STATUS_VALUES: tuple[str, ...] = ("planned", "planted", "paid", "dropped")
STATUS_LABELS: dict[str, str] = {
    "planned": "规划中",
    "planted": "已埋",
    "paid": "已收",
    "dropped": "已弃",
}

# 旧词表的值：P1c 时伏笔复用了章节状态。存量数据里可能有，不静默改数据，
# 归一成 planned 并让界面标出「旧值」。
LEGACY_VALUES = {"confirmed": "planned"}

_LABELS_BY_LABEL = {label: key for key, label in STATUS_LABELS.items()}


def normalize_status(value: Any, *, default: str = "planned") -> str:
    """接受英文键或中文标签；旧值归一；未知值报错。"""
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        return default
    if text in STATUS_VALUES:
        return text
    if text in LEGACY_VALUES:
        return LEGACY_VALUES[text]
    return _LABELS_BY_LABEL.get(text, None) or _unknown(value)


def _unknown(value: Any) -> str:
    raise ValueError(
        f"未知的伏笔状态「{value}」，可用值：{' / '.join(STATUS_VALUES)}"
    )


def is_legacy(value: Any) -> bool:
    text = value.strip() if isinstance(value, str) else ""
    return text in LEGACY_VALUES


def effective_status(row) -> str:
    """状态与位置字段的一致性：**事实优先于判断，只有 `dropped` 例外**。

    - 显式 `dropped` → `dropped`（作者的判断，位置字段不改它）；
    - 其余情况 `actual_pay_scene_id` 非空 → `paid`（正文里已经收了是事实）；
    - 显式 `paid` / `planted` 原样返回；
    - `planned` 且已埋设 → `planted`。

    位置是事实、状态是判断。作者说「这条我不收了」，埋设位置还在，不该把它
    翻回 `planted` —— 那是唯一让判断压过事实的地方。反过来，作者早先标过
    `planted`、之后回写助手经他确认记下了实际回收，若还显示「已埋」，同一行
    里状态列与「实际回收位置」列会互相打架；事实应当赢。
    """
    explicit = row.status or "planned"
    if explicit == "dropped":
        return "dropped"
    if row.actual_pay_scene_id:
        return "paid"
    if explicit in ("paid", "planted"):
        return explicit
    if row.plant_scene_id:
        return "planted"
    return "planned"
