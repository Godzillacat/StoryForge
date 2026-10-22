from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.schemas import ReviewMarkClear, ReviewMarkCreate
from app.db.session import get_session
from app.services import impact_service, review_service

router = APIRouter(prefix="/api", tags=["impact"])

_MISSING_PREFIXES = (
    "项目不存在",
    "这个项目还没有故事圣经",
    "设定条目不存在",
    "卷不存在",
    "章不存在",
    "场景不存在",
    "待复核标记不存在",
)


def _error(exc: ValueError) -> HTTPException:
    message = str(exc)
    if message.startswith(_MISSING_PREFIXES):
        return HTTPException(status_code=404, detail=message)
    return HTTPException(status_code=400, detail=message)


@router.get("/projects/{project_id}/impact")
def analyze_impact(
    project_id: str,
    target_type: str = Query(...),
    target_id: str = Query(...),
    session: Session = Depends(get_session),
) -> dict:
    try:
        return impact_service.analyze(session, project_id, target_type, target_id)
    except ValueError as exc:
        raise _error(exc) from exc


@router.get("/projects/{project_id}/review-marks")
def list_marks(project_id: str, session: Session = Depends(get_session)) -> list[dict]:
    try:
        return review_service.list_marks(session, project_id)
    except ValueError as exc:
        raise _error(exc) from exc


@router.post("/projects/{project_id}/review-marks")
def add_marks(
    project_id: str, payload: ReviewMarkCreate, session: Session = Depends(get_session)
) -> dict:
    try:
        added = review_service.add_marks(
            session, project_id, [item.model_dump() for item in payload.items]
        )
        rows = review_service.list_marks(session, project_id)
    except ValueError as exc:
        raise _error(exc) from exc
    return {"added": added, "marks": rows}


@router.post("/projects/{project_id}/review-marks/clear")
def clear_marks(
    project_id: str, payload: ReviewMarkClear, session: Session = Depends(get_session)
) -> dict:
    try:
        removed = review_service.clear_marks(
            session, project_id, [item.model_dump() for item in payload.items]
        )
        rows = review_service.list_marks(session, project_id)
    except ValueError as exc:
        raise _error(exc) from exc
    return {"removed": removed, "marks": rows}


@router.delete("/review-marks/{mark_id}", status_code=204)
def clear_mark(mark_id: str, session: Session = Depends(get_session)) -> None:
    try:
        review_service.clear_mark(session, mark_id)
    except ValueError as exc:
        raise _error(exc) from exc
