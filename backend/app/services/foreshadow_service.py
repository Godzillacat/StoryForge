"""伏笔的唯一真相：公开 CRUD，以及场景挂接用的按名称查找/新建。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chapter_types import normalize_status
from app.db.models import Foreshadow, Scene


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


def list_foreshadows(session: Session, project_id: str) -> list[Foreshadow]:
    return list(
        session.scalars(
            select(Foreshadow)
            .where(Foreshadow.project_id == project_id)
            .order_by(Foreshadow.created_at)
        )
    )


def _clean_name(value: str | None) -> str:
    name = (value or "").strip()
    if not name:
        raise ValueError("伏笔名不能为空")
    return name


def _checked_scene_id(session: Session, project_id: str, scene_id: str) -> str:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise ValueError(f"场景不存在：{scene_id}")
    if get_project_for_scene(session, scene) != project_id:
        raise ValueError(f"场景不属于这个项目：{scene_id}")
    return scene_id


def create_foreshadow(session: Session, project_id: str, **fields) -> Foreshadow:
    name = _clean_name(fields.get("name"))
    if find_by_name(session, project_id, name) is not None:
        raise ValueError(f"这个项目里已经有叫「{name}」的伏笔了")
    actual = fields.get("actual_pay_scene_id") or None
    if actual:
        actual = _checked_scene_id(session, project_id, actual)
    row = Foreshadow(
        project_id=project_id,
        name=name,
        note=fields.get("note") or "",
        status=normalize_status(fields.get("status")),
        actual_pay_scene_id=actual,
        source_run_id=fields.get("source_run_id"),
    )
    session.add(row)
    session.commit()
    return row


def update_foreshadow(session: Session, foreshadow_id: str, **fields) -> Foreshadow:
    row = session.get(Foreshadow, foreshadow_id)
    if row is None:
        raise ValueError(f"伏笔不存在：{foreshadow_id}")
    # 先验后改：任一步校验失败都回滚，调用方拿不到半截改动。
    try:
        if "name" in fields:
            name = _clean_name(fields.get("name"))
            other = find_by_name(session, row.project_id, name)
            if other is not None and other.id != row.id:
                raise ValueError(f"这个项目里已经有叫「{name}」的伏笔了")
            row.name = name
        if "note" in fields:
            row.note = fields.get("note") or ""
        if "plan_pay_scene_id" in fields:
            scene_id = fields.get("plan_pay_scene_id")
            if scene_id:
                _checked_scene_id(session, row.project_id, scene_id)
            row.plan_pay_scene_id = scene_id or None
        if "actual_pay_scene_id" in fields:
            scene_id = fields.get("actual_pay_scene_id")
            if scene_id:
                _checked_scene_id(session, row.project_id, scene_id)
            row.actual_pay_scene_id = scene_id or None
        if "status" in fields:
            row.status = normalize_status(fields.get("status"))
        session.commit()
    except Exception:
        session.rollback()
        raise
    return row


def delete_foreshadow(session: Session, foreshadow_id: str) -> None:
    row = session.get(Foreshadow, foreshadow_id)
    if row is None:
        raise ValueError(f"伏笔不存在：{foreshadow_id}")
    session.delete(row)
    session.commit()


def get_project_for_scene(session: Session, scene: Scene) -> str:
    from app.services.chapter_service import get_project_for_chapter

    return get_project_for_chapter(session, scene.chapter_id).id
