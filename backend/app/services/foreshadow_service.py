"""伏笔的唯一真相：按名称查找/新建（本任务），公开 CRUD 在 Task 4 补齐。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Foreshadow


def find_by_name(session: Session, project_id: str, name: str) -> Foreshadow | None:
    return session.scalars(
        select(Foreshadow).where(
            Foreshadow.project_id == project_id, Foreshadow.name == name.strip()
        )
    ).first()


def find_or_create(
    session: Session, project_id: str, name: str, source_run_id: str | None = None
) -> Foreshadow:
    clean = name.strip()
    if not clean:
        raise ValueError("伏笔名不能为空")
    existing = find_by_name(session, project_id, clean)
    if existing is not None:
        return existing
    foreshadow = Foreshadow(
        project_id=project_id, name=clean, source_run_id=source_run_id
    )
    session.add(foreshadow)
    session.flush()
    return foreshadow
