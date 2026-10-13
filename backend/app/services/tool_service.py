from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ToolTemplate


def list_tools(session: Session, category: str | None = None) -> list[ToolTemplate]:
    stmt = select(ToolTemplate).order_by(ToolTemplate.category, ToolTemplate.key)
    if category:
        stmt = stmt.where(ToolTemplate.category == category)
    return list(session.scalars(stmt))
