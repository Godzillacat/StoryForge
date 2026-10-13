from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class ToolTemplate(IdMixin, TimestampMixin, Base):
    """创作工具库模板。builtin=True 时来自 app/tools_lib，project_id 为空。"""

    __tablename__ = "tool_template"

    key: Mapped[str] = mapped_column(String(100), index=True)
    category: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    definition_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    checklist_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    builtin: Mapped[bool] = mapped_column(Boolean, default=True)
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), default=None
    )
