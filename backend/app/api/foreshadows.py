from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import ForeshadowCreate, ForeshadowUpdate
from app.db.session import get_session
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
        "source_run_id": row.source_run_id,
    }


@router.get("/projects/{project_id}/foreshadows")
def list_foreshadows(
    project_id: str, session: Session = Depends(get_session)
) -> list[dict]:
    return [_out(row) for row in foreshadow_service.list_foreshadows(session, project_id)]


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
