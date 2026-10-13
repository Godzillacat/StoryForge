from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Idea(IdMixin, TimestampMixin, Base):
    __tablename__ = "idea"

    project_id: Mapped[str] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), index=True)
    # 作者原话。任何 AI 产出都不得写进这个字段（D-04）
    raw_text: Mapped[str] = mapped_column(Text)
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    parsed_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    status: Mapped[str] = mapped_column(String(30), default="raw")
