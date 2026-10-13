from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Project(IdMixin, TimestampMixin, Base):
    __tablename__ = "project"

    name: Mapped[str] = mapped_column(String(200))
    genre: Mapped[str | None] = mapped_column(String(100), default=None)
    sub_genre: Mapped[str | None] = mapped_column(String(100), default=None)
    tone: Mapped[str | None] = mapped_column(String(200), default=None)
    target_length: Mapped[int | None] = mapped_column(default=None)
    writing_lang: Mapped[str] = mapped_column(String(20), default="zh")
    cover_path: Mapped[str | None] = mapped_column(String(500), default=None)
    # P1a 只存不用，P2 的逻辑自检会读它
    logic_check_level: Mapped[str] = mapped_column(String(20), default="loose")
    summary: Mapped[str | None] = mapped_column(Text, default=None)
