from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.services import tool_service

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("")
def list_tools(
    category: str | None = None, session: Session = Depends(get_session)
) -> list[dict]:
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
        for t in tool_service.list_tools(session, category)
    ]
