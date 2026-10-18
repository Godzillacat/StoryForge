from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.services import project_service, search_service

router = APIRouter(prefix="/api", tags=["search"])

_ALLOWED_TYPES = {"entry", "chapter", "scene"}


@router.get("/projects/{project_id}/search")
def search_project(
    project_id: str,
    q: str = Query(...),
    limit: int = Query(20),
    types: str | None = None,
    session: Session = Depends(get_session),
) -> dict:
    """全文检索。首次检索可能触发该项目的索引重建并提交索引状态。"""
    if project_service.get_project(session, project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not q.strip() or len(q) > 200:
        raise HTTPException(status_code=400, detail="检索词长度必须在 1–200 之间")
    if not 1 <= limit <= 50:
        raise HTTPException(status_code=400, detail="limit 必须在 1–50 之间")

    entity_types: list[str] | None = None
    if types:
        entity_types = [item.strip() for item in types.split(",") if item.strip()]
        invalid = [item for item in entity_types if item not in _ALLOWED_TYPES]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"未知的检索类型：{', '.join(invalid)}",
            )

    try:
        hits = search_service.search(
            session,
            project_id,
            q,
            entity_types=entity_types,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "query": q,
        "results": [
            {
                "entity_type": hit.entity_type,
                "entity_id": hit.entity_id,
                "subtype": hit.subtype,
                "title": hit.title,
                "snippet": hit.snippet,
            }
            for hit in hits
        ],
    }
