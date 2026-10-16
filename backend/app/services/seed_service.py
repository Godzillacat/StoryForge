"""预置数据落库。幂等：已存在则跳过，方便每次启动调用。"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.roster import DEFAULT_ROSTER
from app.db.models import Agent, AgentVersion, ToolTemplate

TOOLS_LIB_DIR = Path(__file__).resolve().parent.parent / "tools_lib"


def seed_agents(session: Session) -> int:
    created = 0
    for entry in DEFAULT_ROSTER:
        existing = session.scalars(select(Agent).where(Agent.name == entry["name"])).first()
        if existing is not None:
            continue
        agent = Agent(
            name=entry["name"],
            role_label=entry["role_label"],
            color=entry["color"],
            task_type=entry["task_type"],
            builtin=True,
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
        )
        session.add(version)
        session.flush()
        agent.current_version_id = version.id
        created += 1
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
