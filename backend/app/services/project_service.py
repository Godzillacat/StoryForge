from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Project


def list_projects(session: Session) -> list[Project]:
    return list(session.scalars(select(Project).order_by(Project.created_at.desc())))


def create_project(session: Session, **fields) -> Project:
    project = Project(**fields)
    session.add(project)
    session.commit()
    return project


def get_project(session: Session, project_id: str) -> Project | None:
    return session.get(Project, project_id)


def update_project(session: Session, project_id: str, **fields) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError(f"项目不存在：{project_id}")
    for key, value in fields.items():
        if value is not None:
            setattr(project, key, value)
    session.commit()
    return project


def delete_project(session: Session, project_id: str) -> None:
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError(f"项目不存在：{project_id}")
    session.delete(project)
    session.commit()
