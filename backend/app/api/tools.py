from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ToolTemplate
from app.db.session import get_session

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("")
def list_tools(
    category: str | None = None, session: Session = Depends(get_session)
) -> list[dict]:
    stmt = select(ToolTemplate).order_by(ToolTemplate.category, ToolTemplate.key)
    if category:
        stmt = stmt.where(ToolTemplate.category == category)
    return [
        {
            "id": t.id,
            "key": t.key,
            "category": t.category,
            "name": t.name,
            "description": t.description,
            "definition": t.definition_json,
            "checklist": t.checklist_json,
            "builtin": t.builtin,
        }
        for t in session.scalars(stmt)
    ]
