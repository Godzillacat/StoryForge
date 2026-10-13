from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import ArchitectureAdopt
from app.db.session import get_session
from app.services import agent_service, architecture_service
from app.services.runtime_service import RuntimeService

router = APIRouter(prefix="/api/projects", tags=["architecture"])


@router.get("/{project_id}/architecture")
def get_architecture(project_id: str, session: Session = Depends(get_session)) -> dict:
    arch, acts = architecture_service.get_architecture(session, project_id)
    return {
        "architecture": _arch_out(arch),
        "acts": [_act_out(a) for a in acts],
    }


@router.post("/{project_id}/architecture/recommend")
def recommend(project_id: str, session: Session = Depends(get_session)) -> dict:
    architect = agent_service.find_by_task_type(session, "architecture")
    if architect is None:
        raise HTTPException(status_code=500, detail="找不到架构师智能体，请重新预置阵容")

    service = RuntimeService(session)
    try:
        run, result = service.execute(project_id, architect.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "run": {
            "id": run.id,
            "agent_id": run.agent_id,
            "agent_version_id": run.agent_version_id,
            "provider_id": run.provider_id,
            "model": run.model,
            "params": run.params_json,
            "rendered_prompt": run.rendered_prompt,
            "raw_output": run.raw_output,
            "parsed_json": run.parsed_json,
            "structured": run.structured,
            "parse_error": run.parse_error,
            "prompt_tokens": run.prompt_tokens,
            "completion_tokens": run.completion_tokens,
            "cost_estimate": run.cost_estimate,
            "duration_ms": run.duration_ms,
            "status": run.status,
            "error": run.error_json,
            "trimmed": run.trimmed_json,
            "created_at": run.created_at.isoformat(),
        },
        "options": (result.parsed or {}).get("options", []) if result.structured else [],
        "story_bible_v0": (result.parsed or {}).get("story_bible_v0", {}) if result.structured else {},
        "structured": result.structured,
        "parse_error": result.parse_error,
        "raw_text": result.raw_output,
    }


@router.put("/{project_id}/architecture")
def adopt(project_id: str, payload: ArchitectureAdopt, session: Session = Depends(get_session)) -> dict:
    """作者确认后写入项目结构。这是「AI 出候选、作者拍板」的落点。"""
    arch, acts = architecture_service.adopt(session, project_id, payload.model_dump())
    return {"architecture": _arch_out(arch), "acts": [_act_out(a) for a in acts]}


def _arch_out(arch) -> dict | None:
    if arch is None:
        return None
    return {
        "id": arch.id,
        "tool_ref": arch.tool_ref,
        "logline": arch.logline,
        "theme": arch.theme,
        "premise": arch.premise,
        "ending_direction": arch.ending_direction,
        "locked": arch.locked,
    }


def _act_out(act) -> dict:
    return {
        "id": act.id,
        "seq": act.seq,
        "name": act.name,
        "purpose": act.purpose,
        "target_word_ratio": act.target_word_ratio,
        "summary": act.summary,
    }
