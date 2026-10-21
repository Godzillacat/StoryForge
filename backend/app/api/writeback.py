"""状态与伏笔回写接口。路由层只做参数校验、错误翻译与调用。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import WritebackApply
from app.db.session import get_session
from app.services import writeback_service

router = APIRouter(prefix="/api", tags=["writeback"])


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    if message.startswith("场景不存在"):
        return HTTPException(status_code=404, detail=message)
    if message.startswith("场景的章节结构已损坏"):
        return HTTPException(status_code=409, detail=message)
    return HTTPException(status_code=400, detail=message)


@router.post("/scenes/{scene_id}/writeback")
def suggest_writeback(
    scene_id: str, session: Session = Depends(get_session)
) -> dict:
    try:
        return writeback_service.suggest(session, scene_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.post("/scenes/{scene_id}/writeback/apply")
def apply_writeback(
    scene_id: str,
    payload: WritebackApply,
    session: Session = Depends(get_session),
) -> dict:
    try:
        return writeback_service.apply(session, scene_id, payload.model_dump())
    except ValueError as exc:
        raise _value_error(exc) from exc
