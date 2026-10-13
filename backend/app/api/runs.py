from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api._serializers import _run_out
from app.api.schemas import RunRequest
from app.db.session import get_session
from app.services import run_service
from app.services.runtime_service import RuntimeService

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("")
def list_runs(
    project_id: str | None = Query(default=None),
    agent_id: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    session: Session = Depends(get_session),
) -> list[dict]:
    return [_run_out(r) for r in run_service.list_runs(session, project_id, agent_id, limit)]


@router.get("/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    run = run_service.get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return _run_out(run)


@router.post("", status_code=201)
def run_agent(payload: RunRequest, session: Session = Depends(get_session)) -> dict:
    """调试台入口：跑一次智能体，返回完整链路。"""
    service = RuntimeService(session)
    try:
        run, result = service.execute(payload.project_id, payload.agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"run": _run_out(run), "parse_error": result.parse_error, "trimmed": result.trimmed}
