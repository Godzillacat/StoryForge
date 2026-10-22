"""改动历史：按目标对象粒度的记录与查询（产品 §4.11）。

`record` **只 add、不 commit** —— 由调用方的业务事务一起提交。这样业务
回滚时日志跟着回滚，不会出现「记了一笔根本没发生的事」。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ChangeLog, Project

TARGET_TYPES: dict[str, str] = {
    "scene": "场景",
    "chapter": "章",
    "volume": "卷",
    "entry": "设定条目",
    "architecture": "故事圣经",
    "snapshot": "快照",
    "project": "项目",
}

ACTIONS: dict[str, str] = {
    "create": "新建",
    "update": "编辑",
    "delete": "删除",
    "adopt": "采纳",
    "restore": "恢复",
    "rollback": "回滚",
}

SOURCES: dict[str, str] = {
    "author": "作者",
    "ai": "AI",
    "snapshot": "快照",
}


def record(
    session: Session,
    project_id: str,
    *,
    target_type: str,
    target_id: str,
    target_label: str,
    action: str,
    source: str = "author",
    summary: str = "",
) -> ChangeLog:
    """写一条记录。不提交 —— 必须与业务改动在同一事务里。"""
    row = ChangeLog(
        project_id=project_id,
        target_type=target_type,
        target_id=target_id,
        target_label=(target_label or "").strip()[:200],
        action=action,
        source=source,
        summary=summary or "",
    )
    session.add(row)
    return row


def serialize(row: ChangeLog) -> dict:
    return {
        "id": row.id,
        "project_id": row.project_id,
        "target_type": row.target_type,
        "target_type_label": TARGET_TYPES.get(row.target_type, row.target_type),
        "target_id": row.target_id,
        "target_label": row.target_label,
        "action": row.action,
        "action_label": ACTIONS.get(row.action, row.action),
        "source": row.source,
        "source_label": SOURCES.get(row.source, row.source),
        "summary": row.summary,
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


def list_changes(
    session: Session,
    project_id: str,
    *,
    target_type: str | None = None,
    target_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    if session.get(Project, project_id) is None:
        raise ValueError(f"项目不存在：{project_id}")
    if target_type and target_type not in TARGET_TYPES:
        raise ValueError(f"未知的历史目标类型：{target_type}")
    query = select(ChangeLog).where(ChangeLog.project_id == project_id)
    if target_type:
        query = query.where(ChangeLog.target_type == target_type)
    if target_id:
        query = query.where(ChangeLog.target_id == target_id)
    # 同一次事务里写的一批记录时间戳相同；用 id 兜底保证顺序稳定。
    rows = list(
        session.scalars(
            query.order_by(ChangeLog.created_at.desc(), ChangeLog.id.desc())
            .offset(max(0, offset))
            .limit(max(1, min(limit, 200)))
        )
    )
    return {
        "changes": [serialize(row) for row in rows],
        "target_types": [{"key": k, "label": v} for k, v in TARGET_TYPES.items()],
    }
