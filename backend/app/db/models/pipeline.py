"""管线编排：一条按项目走的流水线，以及它的运行记录。

**运行节点是快照**：开始运行后作者可能去改管线，若运行器每步都读当前管线，
改一次顺序就会让进行中的运行错位。所以 `pipeline_run_node` 把 name /
task_type / agent_id 复制一份，并把 `pipeline_id` 记成普通字符串而不是外键 ——
管线被改或删都不该影响历史运行。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Pipeline(IdMixin, TimestampMixin, Base):
    __tablename__ = "pipeline"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), unique=True, index=True
    )
    # every | key_only | auto
    policy: Mapped[str] = mapped_column(String(20), default="key_only")


class PipelineNode(IdMixin, TimestampMixin, Base):
    __tablename__ = "pipeline_node"
    __table_args__ = (Index("ix_pipeline_node_pipeline", "pipeline_id", "seq"),)

    pipeline_id: Mapped[str] = mapped_column(
        ForeignKey("pipeline.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(120))
    task_type: Mapped[str] = mapped_column(String(40))
    # 空 = 按 task_type 取第一个启用的智能体
    agent_id: Mapped[str | None] = mapped_column(String(36), default=None)
    checkpoint: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    target_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class PipelineRun(IdMixin, TimestampMixin, Base):
    __tablename__ = "pipeline_run"
    __table_args__ = (Index("ix_pipeline_run_project", "project_id", "created_at"),)

    project_id: Mapped[str] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    # 快照引用，不建外键：管线被改或删都不影响历史运行
    pipeline_id: Mapped[str] = mapped_column(String(36), default="")
    # 运行时快照，之后改策略不影响进行中的运行
    policy: Mapped[str] = mapped_column(String(20), default="key_only")
    # running | paused | awaiting | completed | cancelled | failed
    status: Mapped[str] = mapped_column(String(20), default="paused")
    cursor: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")


class PipelineRunNode(IdMixin, TimestampMixin, Base):
    __tablename__ = "pipeline_run_node"
    __table_args__ = (Index("ix_pipeline_run_node_run", "run_id", "seq"),)

    run_id: Mapped[str] = mapped_column(
        ForeignKey("pipeline_run.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer, default=0)
    # 以下三项是运行开始时的快照
    name: Mapped[str] = mapped_column(String(120), default="")
    task_type: Mapped[str] = mapped_column(String(40), default="")
    agent_id: Mapped[str | None] = mapped_column(String(36), default=None)

    # pending | running | ok | awaiting | blocked | skipped | failed | cancelled
    status: Mapped[str] = mapped_column(String(20), default="pending")
    generation_run_id: Mapped[str | None] = mapped_column(String(36), default=None)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    message: Mapped[str] = mapped_column(Text, default="")
