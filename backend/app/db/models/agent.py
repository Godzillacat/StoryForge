from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Agent(IdMixin, TimestampMixin, Base):
    __tablename__ = "agent"
    __table_args__ = (Index("uq_agent_preset_key", "preset_key", unique=True),)

    name: Mapped[str] = mapped_column(String(120))
    # 代码里的稳定预置 key。按名字判重会在作者改名后造出重复角色卡。
    preset_key: Mapped[str | None] = mapped_column(String(60), default=None)
    role_label: Mapped[str] = mapped_column(String(60), default="")
    color: Mapped[str] = mapped_column(String(20), default="#6366f1")
    task_type: Mapped[str] = mapped_column(String(40), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    builtin: Mapped[bool] = mapped_column(Boolean, default=True)
    current_version_id: Mapped[str | None] = mapped_column(String(36), default=None)


class AgentVersion(IdMixin, TimestampMixin, Base):
    """不可变快照。改提示词 = 插入新版本并移动 Agent.current_version_id（D-06）。"""

    __tablename__ = "agent_version"

    agent_id: Mapped[str] = mapped_column(ForeignKey("agent.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int] = mapped_column(default=1)
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    model_binding_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    param_profile: Mapped[str] = mapped_column(String(30), default="balanced")
    context_slots_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    output_schema_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    skills_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    trigger_mode: Mapped[str] = mapped_column(String(20), default="manual")
    note: Mapped[str] = mapped_column(Text, default="")
    # 该版本来自哪一份预置内容；作者编辑出的版本永远为 None。
    preset_fingerprint: Mapped[str | None] = mapped_column(String(64), default=None)
