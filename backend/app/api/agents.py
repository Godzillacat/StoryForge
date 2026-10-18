from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import AgentUpdate, VersionCreate
from app.db.session import get_session
from app.services import agent_service, preset_service

router = APIRouter(prefix="/api/agents", tags=["agents"])


def _version_out(version) -> dict | None:
    if version is None:
        return None
    return {
        "id": version.id,
        "version_no": version.version_no,
        "system_prompt": version.system_prompt,
        "model_binding_json": version.model_binding_json,
        "param_profile": version.param_profile,
        "context_slots_json": version.context_slots_json,
        "output_schema_json": version.output_schema_json,
        "skills_json": version.skills_json,
        "trigger_mode": version.trigger_mode,
        "note": version.note,
        "created_at": version.created_at.isoformat(),
    }


def _agent_out(agent, version) -> dict:
    return {
        "id": agent.id,
        "name": agent.name,
        "role_label": agent.role_label,
        "color": agent.color,
        "task_type": agent.task_type,
        "enabled": agent.enabled,
        "builtin": agent.builtin,
        "preset": preset_service.status_for(agent, version),
        "current_version": _version_out(version),
    }


@router.get("")
def list_agents(session: Session = Depends(get_session)) -> list[dict]:
    out = []
    for agent in agent_service.list_agents(session):
        version = agent_service.get_version(session, agent.current_version_id) if agent.current_version_id else None
        out.append(_agent_out(agent, version))
    return out


@router.patch("/{agent_id}")
def update_agent(
    agent_id: str, payload: AgentUpdate, session: Session = Depends(get_session)
) -> dict:
    try:
        agent = agent_service.update_agent(
            session, agent_id, **payload.model_dump(exclude_none=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    version = (
        agent_service.get_version(session, agent.current_version_id)
        if agent.current_version_id
        else None
    )
    return _agent_out(agent, version)


@router.get("/{agent_id}/versions")
def list_versions(agent_id: str, session: Session = Depends(get_session)) -> list[dict]:
    return [_version_out(v) for v in agent_service.list_versions(session, agent_id)]


@router.post("/{agent_id}/versions", status_code=201)
def create_version(agent_id: str, payload: VersionCreate, session: Session = Depends(get_session)) -> dict:
    try:
        version = agent_service.create_version(
            session, agent_id, **payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _version_out(version)


@router.post("/{agent_id}/apply-preset")
def apply_preset(agent_id: str, session: Session = Depends(get_session)) -> dict:
    agent = agent_service.get_agent(session, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"智能体不存在：{agent_id}")
    try:
        preset_service.apply_preset(session, agent)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    version = (
        agent_service.get_version(session, agent.current_version_id)
        if agent.current_version_id
        else None
    )
    return _agent_out(agent, version)


@router.post("/{agent_id}/rollback/{version_id}")
def rollback(agent_id: str, version_id: str, session: Session = Depends(get_session)) -> dict:
    try:
        agent = agent_service.rollback_to(session, agent_id, version_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    version = agent_service.get_version(session, agent.current_version_id)
    return _agent_out(agent, version)
