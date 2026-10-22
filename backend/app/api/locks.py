from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import LockUpdate, ParagraphLocks
from app.db.session import get_session
from app.services.lock_service import (
    get_locked,
    paragraph_locks,
    set_locked,
    set_paragraph_locks,
)
from app.lock_types import LOCK_TARGETS

router = APIRouter(prefix="/api", tags=["locks"])

_MISSING_PREFIXES = ("故事圣经不存在", "设定条目不存在", "卷不存在", "章不存在", "场景不存在")


def _error(exc: ValueError) -> HTTPException:
    if str(exc).startswith(_MISSING_PREFIXES):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/lock-targets")
def list_lock_targets() -> dict:
    """目标类型清单的唯一真相在 app/lock_types.py，这里只做投影。"""
    return {"targets": [{"key": k, "label": v} for k, v in LOCK_TARGETS.items()]}


@router.get("/locks/{target_type}/{target_id}")
def read_lock(
    target_type: str, target_id: str, session: Session = Depends(get_session)
) -> dict:
    try:
        return get_locked(session, target_type, target_id)
    except ValueError as exc:
        raise _error(exc) from exc


@router.patch("/locks/{target_type}/{target_id}")
def write_lock(
    target_type: str,
    target_id: str,
    payload: LockUpdate,
    session: Session = Depends(get_session),
) -> dict:
    try:
        return set_locked(session, target_type, target_id, payload.locked)
    except ValueError as exc:
        raise _error(exc) from exc


@router.get("/scenes/{scene_id}/paragraph-locks")
def read_paragraph_locks(scene_id: str, session: Session = Depends(get_session)) -> dict:
    try:
        return {"scene_id": scene_id, "paragraphs": paragraph_locks(session, scene_id)}
    except ValueError as exc:
        raise _error(exc) from exc


@router.put("/scenes/{scene_id}/paragraph-locks")
def write_paragraph_locks(
    scene_id: str, payload: ParagraphLocks, session: Session = Depends(get_session)
) -> dict:
    try:
        rows = set_paragraph_locks(session, scene_id, payload.paragraphs)
    except ValueError as exc:
        raise _error(exc) from exc
    return {"scene_id": scene_id, "paragraphs": rows}
