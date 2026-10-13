from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Architecture(IdMixin, TimestampMixin, Base):
    __tablename__ = "architecture"

    project_id: Mapped[str] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), index=True)
    tool_ref: Mapped[str | None] = mapped_column(String(100), default=None)
    logline: Mapped[str | None] = mapped_column(Text, default=None)
    theme: Mapped[str | None] = mapped_column(Text, default=None)
    premise: Mapped[str | None] = mapped_column(Text, default=None)
    ending_direction: Mapped[str | None] = mapped_column(Text, default=None)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)


class Act(IdMixin, TimestampMixin, Base):
    __tablename__ = "act"

    architecture_id: Mapped[str] = mapped_column(
        ForeignKey("architecture.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(default=0)
    name: Mapped[str] = mapped_column(String(200))
    purpose: Mapped[str | None] = mapped_column(Text, default=None)
    target_word_ratio: Mapped[float | None] = mapped_column(Float, default=None)
    summary: Mapped[str | None] = mapped_column(Text, default=None)
