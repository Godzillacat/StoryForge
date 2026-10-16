from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.schemas import EntryCreate, EntryUpdate
from app.db.session import get_session
from app.services import world_service

router = APIRouter(prefix="/api", tags=["world"])


def _entry_out(entry) -> dict:
    return {
        "id": entry.id,
        "project_id": entry.project_id,
        "type": entry.type,
        "name": entry.name,
        "aliases": entry.aliases_json,
        "tags": entry.tags_json,
        "summary": entry.summary,
        "description": entry.description,
        "hardness": entry.hardness,
        "source_run_id": entry.source_run_id,
        "created_at": entry.created_at.isoformat(),
    }


def _entry_fields(payload: EntryCreate | EntryUpdate) -> dict:
    """只做「未传的字段别覆盖」这一件事；领域名到列名的映射在服务层内部。"""
    return payload.model_dump(exclude_unset=True)


@router.get("/projects/{project_id}/entries")
def list_entries(
    project_id: str,
    type: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[dict]:
    try:
        entries = world_service.list_entries(session, project_id, type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [_entry_out(e) for e in entries]


@router.post("/projects/{project_id}/entries", status_code=201)
def create_entry(
    project_id: str, payload: EntryCreate, session: Session = Depends(get_session)
) -> dict:
    try:
        entry = world_service.create_entry(session, project_id, **_entry_fields(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _entry_out(entry)


@router.patch("/entries/{entry_id}")
def update_entry(
    entry_id: str, payload: EntryUpdate, session: Session = Depends(get_session)
) -> dict:
    try:
        entry = world_service.update_entry(session, entry_id, **_entry_fields(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _entry_out(entry)


@router.delete("/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: str, session: Session = Depends(get_session)) -> None:
    try:
        world_service.delete_entry(session, entry_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
