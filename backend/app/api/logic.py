"""逻辑自检接口。路由层只做参数校验、错误翻译与调用。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import LogicCheckRequest
from app.db.session import get_session
from app.services import logic_service

router = APIRouter(prefix="/api", tags=["logic"])


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    if message.startswith("场景不存在"):
        return HTTPException(status_code=404, detail=message)
    if message.startswith("场景的章节结构已损坏"):
        return HTTPException(status_code=409, detail=message)
    return HTTPException(status_code=400, detail=message)


@router.post("/scenes/{scene_id}/logic-check")
def run_logic_check(
    scene_id: str,
    payload: LogicCheckRequest,
    session: Session = Depends(get_session),
) -> dict:
    try:
        return logic_service.run_logic_check(session, scene_id, payload.stage)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.get("/scenes/{scene_id}/logic-check")
def get_logic_check(
    scene_id: str,
    stage: str = "text",
    session: Session = Depends(get_session),
) -> dict:
    try:
        return logic_service.list_logic_check(session, scene_id, stage)
    except ValueError as exc:
        raise _value_error(exc) from exc
