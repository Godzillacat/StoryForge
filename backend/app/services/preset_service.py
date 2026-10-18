"""预置角色卡的指纹、状态与显式应用。

指纹只覆盖**会影响行为**的版本内容：提示词、上下文槽位、输出契约、参数档、
触发方式。模型绑定、技能勾选、备注是作者侧配置或描述文字，改它们不该提示
「预置有更新」。
"""

from __future__ import annotations

import hashlib
import json

from app.agents.roster import DEFAULT_ROSTER
from app.db.models import Agent, AgentVersion
from app.services import agent_service

_FINGERPRINT_FIELDS = (
    "system_prompt",
    "context_slots_json",
    "output_schema_json",
    "param_profile",
    "trigger_mode",
)


def preset_by_key(key: str | None) -> dict | None:
    if not key:
        return None
    return next((preset for preset in DEFAULT_ROSTER if preset["key"] == key), None)


def _fingerprint(payload: dict) -> str:
    raw = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fingerprint_for_preset(preset: dict) -> str:
    return _fingerprint(
        {
            "system_prompt": preset["system_prompt"],
            "context_slots_json": preset["context_slots"],
            "output_schema_json": preset["output_schema"],
            "param_profile": preset["param_profile"],
            "trigger_mode": preset.get("trigger_mode", "manual"),
        }
    )


def fingerprint_for_version(version: AgentVersion) -> str:
    return _fingerprint(
        {field: getattr(version, field) for field in _FINGERPRINT_FIELDS}
    )


def version_matches_preset(version: AgentVersion, preset: dict) -> bool:
    return fingerprint_for_version(version) == fingerprint_for_preset(preset)


def status_for(agent: Agent, version: AgentVersion | None) -> dict:
    preset = preset_by_key(agent.preset_key)
    if preset is None:
        return {
            "key": None,
            "update_available": False,
            "can_restore": False,
            "up_to_date": False,
        }
    current = fingerprint_for_preset(preset)
    saved = version.preset_fingerprint if version else None
    if saved is None:
        return {
            "key": agent.preset_key,
            "update_available": False,
            "can_restore": True,
            "up_to_date": False,
        }
    if saved == current:
        return {
            "key": agent.preset_key,
            "update_available": False,
            "can_restore": False,
            "up_to_date": True,
        }
    return {
        "key": agent.preset_key,
        "update_available": True,
        "can_restore": True,
        "up_to_date": False,
    }


def apply_preset(session, agent: Agent) -> AgentVersion:
    preset = preset_by_key(agent.preset_key)
    if preset is None:
        raise ValueError("这个智能体没有可用的预置内容")
    current = (
        session.get(AgentVersion, agent.current_version_id)
        if agent.current_version_id
        else None
    )
    fingerprint = fingerprint_for_preset(preset)
    if current is not None and current.preset_fingerprint == fingerprint:
        raise ValueError("预置已是最新")
    # 不传 model_binding_json / skills_json：create_version 从当前版本继承，
    # 那是作者的配置，不该被预置覆盖。
    return agent_service.create_version(
        session,
        agent.id,
        system_prompt=preset["system_prompt"],
        context_slots_json=preset["context_slots"],
        output_schema_json=preset["output_schema"],
        param_profile=preset["param_profile"],
        trigger_mode=preset.get("trigger_mode", "manual"),
        note=preset.get("note", ""),
        preset_fingerprint=fingerprint,
    )
