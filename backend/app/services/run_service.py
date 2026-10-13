from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GenerationRun


def list_runs(
    session: Session,
    project_id: str | None = None,
    agent_id: str | None = None,
    limit: int = 50,
) -> list[GenerationRun]:
    stmt = select(GenerationRun).order_by(GenerationRun.created_at.desc()).limit(limit)
    if project_id:
        stmt = stmt.where(GenerationRun.project_id == project_id)
    if agent_id:
        stmt = stmt.where(GenerationRun.agent_id == agent_id)
    return list(session.scalars(stmt))


def get_run(session: Session, run_id: str) -> GenerationRun | None:
    return session.get(GenerationRun, run_id)
