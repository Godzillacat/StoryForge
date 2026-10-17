"""智能体角色卡与版本管理（D-06）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Agent, AgentVersion


def list_agents(session: Session) -> list[Agent]:
    return list(session.scalars(select(Agent).order_by(Agent.created_at)))


def get_agent(session: Session, agent_id: str) -> Agent | None:
    return session.get(Agent, agent_id)


def find_by_task_type(session: Session, task_type: str) -> Agent | None:
    """取该任务类型下第一个启用的智能体。选题型属于业务判断，放服务层。"""
    return session.scalars(
        select(Agent).where(Agent.task_type == task_type, Agent.enabled.is_(True))
    ).first()


def get_version(session: Session, version_id: str) -> AgentVersion | None:
    return session.get(AgentVersion, version_id)


def create_version(session: Session, agent_id: str, **fields) -> AgentVersion:
    """插入新版本并移动 current_version_id。旧版本保留，可回滚。

    两件事用的是不同的源，别合并：
    - **版本号**取最大版本号 + 1，避免与历史撞号（回滚后新建必然撞）；
    - **内容继承源**取 `current_version_id` 指向的版本，而不是版本号最大的
      那个 —— 回滚之后这两者会分叉，取错会把作者刚弃用的内容悄悄带回来。
    """
    agent = session.get(Agent, agent_id)
    if agent is None:
        raise ValueError(f"智能体不存在：{agent_id}")

    highest = session.scalars(
        select(AgentVersion)
        .where(AgentVersion.agent_id == agent_id)
        .order_by(AgentVersion.version_no.desc())
    ).first()
    base = (
        session.get(AgentVersion, agent.current_version_id)
        if agent.current_version_id
        else None
    ) or highest

    version = AgentVersion(
        agent_id=agent_id,
        version_no=(highest.version_no + 1) if highest else 1,
        system_prompt=fields.get("system_prompt", base.system_prompt if base else ""),
        model_binding_json=fields.get(
            "model_binding_json", base.model_binding_json if base else {}
        ),
        param_profile=fields.get("param_profile", base.param_profile if base else "balanced"),
        context_slots_json=fields.get(
            "context_slots_json", base.context_slots_json if base else []
        ),
        output_schema_json=fields.get(
            "output_schema_json", base.output_schema_json if base else None
        ),
        skills_json=fields.get("skills_json", base.skills_json if base else []),
        trigger_mode=fields.get("trigger_mode", base.trigger_mode if base else "manual"),
        note=fields.get("note", ""),
        # **作者编辑出的版本永远没有指纹。** 若从 base 继承，作者改一版后
        # 系统会误以为它仍是未改动的预置，下一次更新就会覆盖作者的修改。
        preset_fingerprint=fields.get("preset_fingerprint"),
    )
    session.add(version)
    session.flush()
    agent.current_version_id = version.id
    session.commit()
    return version


def rollback_to(session: Session, agent_id: str, version_id: str) -> Agent:
    agent = session.get(Agent, agent_id)
    if agent is None:
        raise ValueError(f"智能体不存在：{agent_id}")
    version = session.get(AgentVersion, version_id)
    if version is None or version.agent_id != agent_id:
        raise ValueError(f"版本不属于该智能体：{version_id}")
    agent.current_version_id = version_id
    session.commit()
    return agent


def list_versions(session: Session, agent_id: str) -> list[AgentVersion]:
    return list(
        session.scalars(
            select(AgentVersion)
            .where(AgentVersion.agent_id == agent_id)
            .order_by(AgentVersion.version_no.desc())
        )
    )


_AGENT_LEVEL_FIELDS = ("name", "role_label", "color", "enabled")


def update_agent(session: Session, agent_id: str, **fields) -> Agent:
    """只改 agent 级字段，不产生新版本。"""
    agent = session.get(Agent, agent_id)
    if agent is None:
        raise ValueError(f"智能体不存在：{agent_id}")
    for key in _AGENT_LEVEL_FIELDS:
        value = fields.get(key)
        if value is not None:
            setattr(agent, key, value)
    session.commit()
    return agent
