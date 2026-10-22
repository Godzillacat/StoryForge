from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api._serializers import _run_out
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
        "run": _run_out(run),
        "options": (result.parsed or {}).get("options", []) if result.structured else [],
        # `.get(key, {})` 的默认值只在**缺键**时生效；模型把可选的 story_bible_v0
        # 写成显式 null 会原样返回 None，前端对结果取 .logline 会抛错。故在边界再兜一次。
        "story_bible_v0": ((result.parsed or {}).get("story_bible_v0") or {})
        if result.structured
        else {},
        "structured": result.structured,
        "parse_error": result.parse_error,
        "raw_text": result.raw_output,
    }


@router.put("/{project_id}/architecture")
def adopt(project_id: str, payload: ArchitectureAdopt, session: Session = Depends(get_session)) -> dict:
    """作者确认后写入项目结构。这是「AI 出候选、作者拍板」的落点。"""
    try:
        arch, acts = architecture_service.adopt(session, project_id, payload.model_dump())
    except ValueError as exc:
        # 锁定是「当前状态不允许」而不是参数错误，与「已在进行中」同一类语义。
        raise HTTPException(status_code=409, detail=str(exc)) from exc
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
