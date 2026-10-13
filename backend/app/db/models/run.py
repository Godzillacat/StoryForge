from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class GenerationRun(IdMixin, TimestampMixin, Base):
    """一次智能体运行的全部审计信息。调试台是这张表的只读视图。"""

    __tablename__ = "generation_run"

    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True, default=None
    )
    agent_id: Mapped[str | None] = mapped_column(String(36), index=True, default=None)
    agent_version_id: Mapped[str | None] = mapped_column(String(36), default=None)
    provider_id: Mapped[str | None] = mapped_column(String(36), default=None)
    model: Mapped[str] = mapped_column(String(120), default="")
    params_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    rendered_prompt: Mapped[str] = mapped_column(Text, default="")
    input_digest: Mapped[str] = mapped_column(String(64), default="")
    raw_output: Mapped[str] = mapped_column(Text, default="")
    parsed_json: Mapped[Any | None] = mapped_column(JSON, default=None)
    structured: Mapped[bool] = mapped_column(Boolean, default=False)
    # 契约校验失败的具体原因。structured=False 时调试台靠它解释为什么
    parse_error: Mapped[str | None] = mapped_column(Text, default=None)
    prompt_tokens: Mapped[int] = mapped_column(default=0)
    completion_tokens: Mapped[int] = mapped_column(default=0)
    cost_estimate: Mapped[float] = mapped_column(Float, default=0.0)
    duration_ms: Mapped[int] = mapped_column(default=0)
    # ok | partial | error
    status: Mapped[str] = mapped_column(String(20), default="ok")
    error_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    trimmed_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
