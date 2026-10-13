from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import IdeaCreate, ProjectCreate, ProjectUpdate
from app.db.session import get_session
from app.services import idea_service, project_service

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _idea_out(idea) -> dict:
    return {
        "id": idea.id,
        "project_id": idea.project_id,
        "raw_text": idea.raw_text,
        "tags": idea.tags_json,
        "parsed_json": idea.parsed_json,
        "status": idea.status,
    }


def _project_out(project) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "genre": project.genre,
        "sub_genre": project.sub_genre,
        "tone": project.tone,
        "target_length": project.target_length,
        "summary": project.summary,
        "writing_lang": project.writing_lang,
        "logic_check_level": project.logic_check_level,
        "created_at": project.created_at.isoformat(),
    }


@router.get("")
def list_projects(session: Session = Depends(get_session)) -> list[dict]:
    return [_project_out(p) for p in project_service.list_projects(session)]


@router.post("", status_code=201)
def create_project(payload: ProjectCreate, session: Session = Depends(get_session)) -> dict:
    return _project_out(project_service.create_project(session, **payload.model_dump()))


@router.get("/{project_id}")
def get_project(project_id: str, session: Session = Depends(get_session)) -> dict:
    project = project_service.get_project(session, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return _project_out(project)


@router.patch("/{project_id}")
def update_project(
    project_id: str, payload: ProjectUpdate, session: Session = Depends(get_session)
) -> dict:
    try:
        project = project_service.update_project(session, project_id, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _project_out(project)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, session: Session = Depends(get_session)) -> None:
    try:
        project_service.delete_project(session, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{project_id}/ideas")
def list_ideas(project_id: str, session: Session = Depends(get_session)) -> list[dict]:
    return [_idea_out(i) for i in idea_service.list_ideas(session, project_id)]


@router.post("/{project_id}/ideas", status_code=201)
def create_idea(project_id: str, payload: IdeaCreate, session: Session = Depends(get_session)) -> dict:
    return _idea_out(idea_service.create_idea(session, project_id, payload.raw_text, payload.tags))
