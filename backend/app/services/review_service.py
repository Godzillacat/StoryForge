"""「待复核」标记：影响面分析发现的下游对象，作者还没重看过。

**显式清除**，不随编辑自动清掉 ——「改过了」与「看过了、决定不改」都该能
清标记；自动清除会让这两种状态与「还没看」无法区分。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    Architecture,
    Chapter,
    Project,
    ReviewMark,
    Scene,
    SettingEntry,
    Volume,
)
from app.lock_types import LOCK_TARGETS, normalize_target_type

_MODEL = {
    "architecture": Architecture,
    "entry": SettingEntry,
    "volume": Volume,
    "chapter": Chapter,
    "scene": Scene,
}


def _project(session: Session, project_id: str) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError(f"项目不存在：{project_id}")
    return project


def add_marks(session: Session, project_id: str, items: list[dict]) -> int:
    """幂等：同一个对象重复标记只留一条，`reason` 更新为最新一次的。

    返回**新增**条数 —— 作者点第二次「标为待复核」时不该看到一个虚假的成功数字。
    """
    _project(session, project_id)
    added = 0
    for item in items:
        kind = normalize_target_type(item.get("target_type"))
        target_id = str(item.get("target_id") or "").strip()
        if not target_id:
            raise ValueError("标为待复核需要指定对象")
        reason = str(item.get("reason") or "").strip()
        existing = session.scalars(
            select(ReviewMark).where(
                ReviewMark.project_id == project_id,
                ReviewMark.target_type == kind,
                ReviewMark.target_id == target_id,
            )
        ).first()
        if existing is not None:
            existing.reason = reason
            continue
        try:
            # 每条一个 SAVEPOINT：并发插入撞唯一约束时只回滚这一条。
            # 整会话 rollback 会把同批前面已经插入的那些一起丢掉，而 added
            # 已经数过它们 —— 一批 10 项丢 9 条还报 10，是最坏的那种静默错。
            with session.begin_nested():
                session.add(
                    ReviewMark(
                        project_id=project_id,
                        target_type=kind,
                        target_id=target_id,
                        reason=reason,
                    )
                )
        except IntegrityError:
            existing = session.scalars(
                select(ReviewMark).where(
                    ReviewMark.project_id == project_id,
                    ReviewMark.target_type == kind,
                    ReviewMark.target_id == target_id,
                )
            ).first()
            if existing is not None:
                existing.reason = reason
            continue
        added += 1
    session.commit()
    return added


def _label(session: Session, mark: ReviewMark) -> str:
    model = _MODEL.get(mark.target_type)
    if model is None:
        return mark.target_id
    row = session.get(model, mark.target_id)
    if row is None:
        return ""
    if mark.target_type == "entry":
        return row.name
    if mark.target_type == "scene":
        chapter = session.get(Chapter, row.chapter_id)
        if chapter is None:
            return f"场景 {row.seq + 1}"
        volume = session.get(Volume, chapter.volume_id)
        if volume is None:
            return f"第{chapter.seq + 1}章 场景{row.seq + 1}"
        return f"第{volume.seq + 1}卷 第{chapter.seq + 1}章 场景{row.seq + 1}"
    if mark.target_type == "chapter":
        return f"第{row.seq + 1}章（{row.title}）"
    if mark.target_type == "volume":
        return f"第{row.seq + 1}卷（{row.name}）"
    return "故事圣经"


def _path(session: Session, mark: ReviewMark) -> str:
    project = mark.project_id
    if mark.target_type == "scene":
        return f"/chapters?project={project}&scene={mark.target_id}"
    if mark.target_type == "chapter":
        return f"/chapters?project={project}&chapter={mark.target_id}"
    if mark.target_type == "volume":
        return f"/chapters?project={project}&volume={mark.target_id}"
    if mark.target_type == "entry":
        return f"/world?project={project}&entry={mark.target_id}"
    return "/architecture"


def serialize_mark(session: Session, mark: ReviewMark) -> dict:
    label = _label(session, mark)
    return {
        "id": mark.id,
        "project_id": mark.project_id,
        "target_type": mark.target_type,
        "type_label": LOCK_TARGETS.get(mark.target_type, mark.target_type),
        "target_id": mark.target_id,
        # 目标已被删除时标签为空 —— 让作者看见的是「这对象没了」而不是一个裸 ID。
        "label": label or "（对象已删除）",
        "reason": mark.reason,
        "path": _path(session, mark),
        "created_at": mark.created_at.isoformat() if mark.created_at else "",
    }


def list_marks(session: Session, project_id: str) -> list[dict]:
    _project(session, project_id)
    rows = session.scalars(
        select(ReviewMark)
        .where(ReviewMark.project_id == project_id)
        .order_by(ReviewMark.created_at.desc())
    ).all()
    return [serialize_mark(session, row) for row in rows]


def clear_mark(session: Session, mark_id: str) -> None:
    mark = session.get(ReviewMark, mark_id)
    if mark is None:
        raise ValueError(f"待复核标记不存在：{mark_id}")
    session.delete(mark)
    session.commit()


def clear_marks(session: Session, project_id: str, items: list[dict]) -> int:
    _project(session, project_id)
    removed = 0
    for item in items:
        kind = normalize_target_type(item.get("target_type"))
        target_id = str(item.get("target_id") or "").strip()
        if not target_id:
            raise ValueError("要清除的标记需要指定对象")
        mark = session.scalars(
            select(ReviewMark).where(
                ReviewMark.project_id == project_id,
                ReviewMark.target_type == kind,
                ReviewMark.target_id == target_id,
            )
        ).first()
        if mark is not None:
            session.delete(mark)
            removed += 1
    session.commit()
    return removed


def clear_for_target(
    session: Session, project_id: str, target_type: str, target_id: str
) -> None:
    """对象被删除时顺手清标记。不提交 —— 由调用方的删除事务一起提交。"""
    mark = session.scalars(
        select(ReviewMark).where(
            ReviewMark.project_id == project_id,
            ReviewMark.target_type == target_type,
            ReviewMark.target_id == target_id,
        )
    ).first()
    if mark is not None:
        session.delete(mark)
