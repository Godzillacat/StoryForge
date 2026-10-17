"""预置数据落库。幂等：已存在则认领并只回填指纹，方便每次启动调用。"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.roster import DEFAULT_ROSTER
from app.db.models import Agent, AgentVersion, ToolTemplate
from app.services import preset_service

TOOLS_LIB_DIR = Path(__file__).resolve().parent.parent / "tools_lib"


def _claim_agent(session: Session, preset: dict) -> tuple[Agent | None, bool]:
    """按稳定身份认领已有角色卡；返回 (agent, 是否该新建)。

    认领顺序：preset_key → 名字 → 唯一 task_type。第三步专门应对作者改过
    内置角色卡名字的情况 —— 以前按名字判重会因此建出重复角色卡。
    多个候选时既不认领也不新建：制造重复比暂时不认领更糟。
    """
    key = preset["key"]
    keyed = session.scalars(
        select(Agent).where(Agent.preset_key == key, Agent.builtin.is_(True))
    ).first()
    if keyed is not None:
        return keyed, False

    candidates = session.scalars(
        select(Agent).where(Agent.builtin.is_(True), Agent.preset_key.is_(None))
    ).all()
    by_name = [agent for agent in candidates if agent.name == preset["name"]]
    if len(by_name) == 1:
        by_name[0].preset_key = key
        session.flush()
        return by_name[0], False

    by_task = [agent for agent in candidates if agent.task_type == preset["task_type"]]
    if len(by_task) == 1:
        by_task[0].preset_key = key
        session.flush()
        return by_task[0], False
    if len(by_task) > 1:
        return None, False
    return None, True


def seed_agents(session: Session) -> int:
    created = 0
    for entry in DEFAULT_ROSTER:
        agent, should_create = _claim_agent(session, entry)
        if should_create:
            agent = Agent(
                name=entry["name"],
                role_label=entry["role_label"],
                color=entry["color"],
                task_type=entry["task_type"],
                builtin=True,
                preset_key=entry["key"],
            )
            session.add(agent)
            session.flush()
            version = AgentVersion(
                agent_id=agent.id,
                version_no=1,
                system_prompt=entry["system_prompt"],
                context_slots_json=entry["context_slots"],
                output_schema_json=entry["output_schema"],
                param_profile=entry["param_profile"],
                trigger_mode=entry.get("trigger_mode", "manual"),
                note=entry.get("note", ""),
                preset_fingerprint=preset_service.fingerprint_for_preset(entry),
            )
            session.add(version)
            session.flush()
            agent.current_version_id = version.id
            created += 1
            continue

        if agent is None:
            # 认领歧义：既不认领也不新建，下一次启动再试。
            continue

        # 已有角色卡：只回填指纹，绝不新建或切换版本。
        version = (
            session.get(AgentVersion, agent.current_version_id)
            if agent.current_version_id
            else None
        )
        if (
            version is not None
            and version.preset_fingerprint is None
            and preset_service.version_matches_preset(version, entry)
        ):
            version.preset_fingerprint = preset_service.fingerprint_for_preset(entry)
    session.commit()
    return created


def seed_tools(session: Session) -> int:
    if not TOOLS_LIB_DIR.is_dir():
        return 0
    created = 0
    for path in sorted(TOOLS_LIB_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        key = payload["key"]
        existing = session.scalars(
            select(ToolTemplate).where(ToolTemplate.key == key, ToolTemplate.builtin.is_(True))
        ).first()
        if existing is not None:
            continue
        session.add(
            ToolTemplate(
                key=key,
                category=payload["category"],
                name=payload["name"],
                description=payload.get("description", ""),
                definition_json=payload.get("definition", {}),
                checklist_json=payload.get("checklist", []),
                builtin=True,
            )
        )
        created += 1
    session.commit()
    return created
