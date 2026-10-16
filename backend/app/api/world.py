from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.schemas import EntryCreate, EntryUpdate, RelationCreate
from app.db.session import get_session
from app.services import world_service
from app.world_types import ENTRY_TYPES, HARDNESS_LEVELS

router = APIRouter(prefix="/api", tags=["world"])


@router.get("/entry-types")
def list_entry_types() -> dict:
    """类型清单的唯一真相在 app/world_types.py，这里只做投影 ——
    前端不必再硬编一份，否则又会出现两份清单互相不一致的老问题。"""
    return {
        "types": [{"key": k, "label": v} for k, v in ENTRY_TYPES.items()],
        "hardness": [{"key": k, "label": v} for k, v in HARDNESS_LEVELS.items()],
    }


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


def _relation_out(relation) -> dict:
    return {
        "id": relation.id,
        "project_id": relation.project_id,
        "from_id": relation.from_id,
        "to_id": relation.to_id,
        "kind": relation.kind,
        "note": relation.note,
    }


@router.get("/projects/{project_id}/relations")
def list_relations(project_id: str, session: Session = Depends(get_session)) -> list[dict]:
    return [_relation_out(r) for r in world_service.list_relations(session, project_id)]


@router.post("/projects/{project_id}/relations", status_code=201)
def create_relation(
    project_id: str, payload: RelationCreate, session: Session = Depends(get_session)
) -> dict:
    try:
        relation = world_service.create_relation(session, project_id, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _relation_out(relation)


@router.delete("/relations/{relation_id}", status_code=204)
def delete_relation(relation_id: str, session: Session = Depends(get_session)) -> None:
    try:
        world_service.delete_relation(session, relation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
