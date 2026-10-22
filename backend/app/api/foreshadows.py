from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import ForeshadowCreate, ForeshadowUpdate
from app.db.session import get_session
from app.foreshadow_types import STATUS_LABELS, effective_status, is_legacy
from app.services import foreshadow_service

router = APIRouter(prefix="/api", tags=["foreshadows"])

# 404 判定用前缀而不是「不存在」子串：伏笔名本身就叫「不存在」时，
# 重名冲突是 400、不能误判成资源缺失（与 chapters.py 同一教训）。
_MISSING_PREFIXES = ("伏笔不存在", "场景不存在")


def _out(row) -> dict:
    return {
        "id": row.id,
        "project_id": row.project_id,
        "name": row.name,
        "note": row.note,
        "plant_scene_id": row.plant_scene_id,
        "plan_pay_scene_id": row.plan_pay_scene_id,
        "actual_pay_scene_id": row.actual_pay_scene_id,
        "status": row.status,
        # 派生值：位置字段反映的事实。作者看到的应该是「它走到哪一步」，
        # 而不是「他最后一次手动点的是哪个值」。
        "effective_status": effective_status(row),
        "status_is_derived": effective_status(row) != (row.status or "planned"),
        "status_is_legacy": is_legacy(row.status),
        "status_label": STATUS_LABELS.get(effective_status(row), effective_status(row)),
        "source_run_id": row.source_run_id,
    }


@router.get("/foreshadow-types")
def list_foreshadow_types() -> dict:
    """状态词表的唯一真相在 app/foreshadow_types.py；前端不硬编第二份。

    与 `/api/chapter-types` 同一形状，但**是另一份词表**：章节的 `confirmed`
    与伏笔的 `paid` 不是一回事。
    """
    return {
        "statuses": [
            {"key": key, "label": label} for key, label in STATUS_LABELS.items()
        ]
    }


@router.get("/projects/{project_id}/foreshadows")
def list_foreshadows(
    project_id: str, session: Session = Depends(get_session)
) -> list[dict]:
    return [_out(row) for row in foreshadow_service.list_foreshadows(session, project_id)]


@router.get("/projects/{project_id}/foreshadows/summary")
def summary(project_id: str, session: Session = Depends(get_session)) -> dict:
    return foreshadow_service.ledger_summary(session, project_id)


@router.post("/projects/{project_id}/foreshadows", status_code=201)
def create_foreshadow(
    project_id: str, payload: ForeshadowCreate, session: Session = Depends(get_session)
) -> dict:
    try:
        row = foreshadow_service.create_foreshadow(
            session, project_id, **payload.model_dump()
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _out(row)


@router.patch("/foreshadows/{foreshadow_id}")
def update_foreshadow(
    foreshadow_id: str, payload: ForeshadowUpdate, session: Session = Depends(get_session)
) -> dict:
    try:
        row = foreshadow_service.update_foreshadow(
            session, foreshadow_id, **payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        if str(exc).startswith(_MISSING_PREFIXES):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _out(row)


@router.delete("/foreshadows/{foreshadow_id}", status_code=204)
def delete_foreshadow(
    foreshadow_id: str, session: Session = Depends(get_session)
) -> None:
    try:
        foreshadow_service.delete_foreshadow(session, foreshadow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
