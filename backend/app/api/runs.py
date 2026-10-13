from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import RunRequest
from app.db.models import GenerationRun
from app.db.session import get_session
from app.services.runtime_service import RuntimeService

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _run_out(run: GenerationRun) -> dict:
    return {
        "id": run.id,
        "project_id": run.project_id,
        "agent_id": run.agent_id,
        "agent_version_id": run.agent_version_id,
        "provider_id": run.provider_id,
        "model": run.model,
        "params": run.params_json,
        "rendered_prompt": run.rendered_prompt,
        "raw_output": run.raw_output,
        "parsed_json": run.parsed_json,
        "structured": run.structured,
        "prompt_tokens": run.prompt_tokens,
        "completion_tokens": run.completion_tokens,
        "cost_estimate": run.cost_estimate,
        "duration_ms": run.duration_ms,
        "status": run.status,
        "error": run.error_json,
        "trimmed": run.trimmed_json,
        "created_at": run.created_at.isoformat(),
    }


@router.get("")
def list_runs(
    project_id: str | None = Query(default=None),
    agent_id: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    session: Session = Depends(get_session),
) -> list[dict]:
    stmt = select(GenerationRun).order_by(GenerationRun.created_at.desc()).limit(limit)
    if project_id:
        stmt = stmt.where(GenerationRun.project_id == project_id)
    if agent_id:
        stmt = stmt.where(GenerationRun.agent_id == agent_id)
    return [_run_out(r) for r in session.scalars(stmt)]


@router.get("/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    run = session.get(GenerationRun, run_id)
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
