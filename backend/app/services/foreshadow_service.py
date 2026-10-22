"""伏笔的唯一真相：公开 CRUD，以及场景挂接用的按名称查找/新建。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.foreshadow_types import effective_status, normalize_status
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


def ledger_summary(session: Session, project_id: str) -> dict:
    """四类计数与回收率。

    `dropped` **不进分母**：作者放弃的伏笔不该拉低回收率 —— 那不是「没收」，
    是「不收了」。分母为 0 时回收率为 0，不是 NaN。
    """
    rows = list_foreshadows(session, project_id)
    counts = {"planned": 0, "planted": 0, "paid": 0, "dropped": 0}
    for row in rows:
        counts[effective_status(row)] += 1
    denominator = counts["paid"] + counts["planted"] + counts["planned"]
    rate = round(counts["paid"] / denominator, 3) if denominator else 0.0
    return {"total": len(rows), **counts, "rate": rate}


def is_unrecovered(row: Foreshadow) -> bool:
    """账本与成品报告共用的「未回收」口径。

    - `paid` 不算（已收）；
    - `dropped` 不算 —— 作者放弃了，那不是「没收」，是「不收了」；
    - 既无埋设也无计划回收的不算 —— 它还没进入进度，没什么可收的。

    只此一处定义：账本计数、成品报告、影响面三处都调它，否则同一个词在三处
    会各自漂移。
    """
    if effective_status(row) in ("paid", "dropped"):
        return False
    return bool(row.plant_scene_id or row.plan_pay_scene_id)


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
