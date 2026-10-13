from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api._serializers import _idea_out, _run_out
from app.db.session import get_session
from app.services import agent_service, idea_service, project_service
from app.services.runtime_service import RuntimeService

router = APIRouter(prefix="/api/projects", tags=["ideas"])


@router.post("/{project_id}/ideas/{idea_id}/parse")
def parse_idea(project_id: str, idea_id: str, session: Session = Depends(get_session)) -> dict:
    """跑灵感解析并写回 parsed_json。返回 run 供调试台展示完整链路。"""
    parsed_text = idea_service.parsed_as_text(session, idea_id)
    if parsed_text is None:
        idea = idea_service.get_idea(session, idea_id)
        if idea is None:
            raise HTTPException(status_code=404, detail="灵感条目不存在")
        if not idea.raw_text.strip():
            raise HTTPException(status_code=400, detail="灵感原话为空，无法解析")

    parser = agent_service.find_by_task_type(session, "idea_parse")
    if parser is None:
        raise HTTPException(status_code=500, detail="找不到灵感解析智能体，请重新预置阵容")

    service = RuntimeService(session)
    try:
        run, result = service.execute(project_id, parser.id, extra={"raw_idea_id": idea_id})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    idea_service.write_parsed(session, idea_id, result.parsed if result.structured else None)
    return {
        "run": _run_out(run),
        "structured": result.structured,
        "parse_error": result.parse_error,
        "idea": _idea_out(idea_service.get_idea(session, idea_id)),
    }
