"""管线词表与默认模板。

默认模板是**代码里的唯一真相**，与预置阵容同一套做法：作者改的是自己项目
的副本，改坏了可以恢复默认。
"""

from __future__ import annotations

PIPELINE_POLICIES = ("every", "key_only", "auto")

POLICY_LABELS = {
    "every": "每步确认",
    "key_only": "仅关键步确认",
    "auto": "连续自动",
}

_DEFAULT_POLICY = "key_only"

RUN_STATUSES = (
    "running",
    "paused",
    "awaiting",
    "completed",
    "cancelled",
    "failed",
)

RUN_STATUS_LABELS = {
    "running": "运行中",
    "paused": "已暂停",
    "awaiting": "等待确认",
    "completed": "已完成",
    "cancelled": "已取消",
    "failed": "失败",
}

NODE_STATUSES = (
    "pending",
    "running",
    "ok",
    "awaiting",
    "blocked",
    "skipped",
    "failed",
    "cancelled",
)

NODE_STATUS_LABELS = {
    "pending": "待执行",
    "running": "执行中",
    "ok": "完成",
    "awaiting": "待确认",
    "blocked": "缺前置",
    "skipped": "已跳过",
    "failed": "失败",
    "cancelled": "已取消",
}

# 检查点标记对应产品 §5.3 的 ★：★拍板（架构）与 ★调整（章纲）。
DEFAULT_PIPELINE = [
    {"name": "灵感解析", "task_type": "idea_parse", "checkpoint": False},
    {"name": "架构推荐", "task_type": "architecture", "checkpoint": True},
    {"name": "世界观补全", "task_type": "worldbuilding", "checkpoint": False},
    {"name": "章纲策划", "task_type": "chapter_plan", "checkpoint": True},
    {"name": "场景卡", "task_type": "scene_plan", "checkpoint": False},
]


def normalize_policy(value: str | None) -> str:
    """未知策略回落默认档：settings 与老库都可能带作者手写过的字符串。"""
    if value in PIPELINE_POLICIES:
        return value
    return _DEFAULT_POLICY


def default_nodes() -> list[dict]:
    """返回新列表 —— 调用方会往节点里塞 id 与 seq，共享同一份会互相污染。"""
    return [dict(node) for node in DEFAULT_PIPELINE]
