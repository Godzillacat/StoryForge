from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.schemas import SnapshotCreate
from app.db.session import get_session
from app.services import change_service, snapshot_service

router = APIRouter(prefix="/api", tags=["snapshots"])

_MISSING_PREFIXES = ("项目不存在", "快照不存在")


def _error(exc: ValueError) -> HTTPException:
    message = str(exc)
    if message.startswith(_MISSING_PREFIXES):
        return HTTPException(status_code=404, detail=message)
    return HTTPException(status_code=400, detail=message)


@router.get("/projects/{project_id}/snapshots")
def list_snapshots(project_id: str, session: Session = Depends(get_session)) -> list[dict]:
    try:
        return snapshot_service.list_snapshots(session, project_id)
    except ValueError as exc:
        raise _error(exc) from exc


@router.post("/projects/{project_id}/snapshots", status_code=201)
def create_snapshot(
    project_id: str, payload: SnapshotCreate, session: Session = Depends(get_session)
) -> dict:
    try:
        row = snapshot_service.create_snapshot(
            session, project_id, payload.name, payload.note
        )
    except ValueError as exc:
        raise _error(exc) from exc
    return snapshot_service.serialize_snapshot(row)


@router.get("/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: str, session: Session = Depends(get_session)) -> dict:
    try:
        return snapshot_service.get_snapshot(session, snapshot_id)
    except ValueError as exc:
        raise _error(exc) from exc


@router.post("/snapshots/{snapshot_id}/restore")
def restore_snapshot(snapshot_id: str, session: Session = Depends(get_session)) -> dict:
    try:
        return snapshot_service.restore_snapshot(session, snapshot_id)
    except ValueError as exc:
        raise _error(exc) from exc


@router.delete("/snapshots/{snapshot_id}", status_code=204)
def delete_snapshot(snapshot_id: str, session: Session = Depends(get_session)) -> None:
    try:
        snapshot_service.delete_snapshot(session, snapshot_id)
    except ValueError as exc:
        raise _error(exc) from exc


@router.get("/projects/{project_id}/changes")
def list_changes(
    project_id: str,
    target_type: str | None = Query(None),
    target_id: str | None = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(get_session),
) -> dict:
    try:
        return change_service.list_changes(
            session,
            project_id,
            target_type=target_type,
            target_id=target_id,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise _error(exc) from exc
