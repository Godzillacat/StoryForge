"""一致性审计接口。路由层只做参数校验、错误翻译与调用。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import AuditResolve
from app.db.session import get_session
from app.services import audit_service

router = APIRouter(prefix="/api", tags=["audit"])


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    if message.startswith(("场景不存在", "审计问题不存在")):
        return HTTPException(status_code=404, detail=message)
    if message.startswith("场景的章节结构已损坏"):
        return HTTPException(status_code=409, detail=message)
    return HTTPException(status_code=400, detail=message)


@router.post("/scenes/{scene_id}/audit")
def run_scene_audit(
    scene_id: str, session: Session = Depends(get_session)
) -> dict:
    try:
        return audit_service.run_audit(session, scene_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.get("/scenes/{scene_id}/audit")
def get_scene_audit(
    scene_id: str, session: Session = Depends(get_session)
) -> dict:
    try:
        return audit_service.list_audit(session, scene_id)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.patch("/audit/issues/{issue_id}")
def resolve_audit_issue(
    issue_id: str,
    payload: AuditResolve,
    session: Session = Depends(get_session),
) -> dict:
    try:
        return audit_service.resolve_issue(session, issue_id, payload.resolution)
    except ValueError as exc:
        raise _value_error(exc) from exc
