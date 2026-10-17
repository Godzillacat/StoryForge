from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.services import timeline_service

router = APIRouter(prefix="/api", tags=["timeline"])


class TimelineEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    story_time: str = ""
    description: str = ""
    participants: list[str] = Field(default_factory=list)
    location_id: str | None = None


class TimelineEventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    story_time: str | None = None
    description: str | None = None
    participants: list[str] | None = None
    location_id: str | None = None


class TimelineMove(BaseModel):
    direction: Literal["up", "down"]


def _event_out(event) -> dict:
    return {
        "id": event.id,
        "project_id": event.project_id,
        "title": event.title,
        "story_time": event.story_time,
        "description": event.description,
        "participants": event.participants_json,
        "location_id": event.location_id,
        "order_index": event.order_index,
        "created_at": event.created_at.isoformat(),
    }


@router.get("/projects/{project_id}/timeline")
def list_timeline(project_id: str, session: Session = Depends(get_session)) -> list[dict]:
    return [_event_out(e) for e in timeline_service.list_events(session, project_id)]


@router.post("/projects/{project_id}/timeline", status_code=201)
def create_event(
    project_id: str, payload: TimelineEventCreate, session: Session = Depends(get_session)
) -> dict:
    try:
        event = timeline_service.create_event(session, project_id, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _event_out(event)


@router.patch("/timeline/{event_id}")
def update_event(
    event_id: str, payload: TimelineEventUpdate, session: Session = Depends(get_session)
) -> dict:
    if timeline_service.get_event(session, event_id) is None:
        raise HTTPException(status_code=404, detail=f"时间线事件不存在：{event_id}")
    try:
        event = timeline_service.update_event(
            session, event_id, **payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _event_out(event)


@router.post("/timeline/{event_id}/move")
def move_event(
    event_id: str, payload: TimelineMove, session: Session = Depends(get_session)
) -> dict:
    if timeline_service.get_event(session, event_id) is None:
        raise HTTPException(status_code=404, detail=f"时间线事件不存在：{event_id}")
    try:
        event = timeline_service.move_event(session, event_id, payload.direction)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _event_out(event)


@router.delete("/timeline/{event_id}", status_code=204)
def delete_event(event_id: str, session: Session = Depends(get_session)) -> None:
    try:
        timeline_service.delete_event(session, event_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
