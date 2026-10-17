from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class TimelineEvent(IdMixin, TimestampMixin, Base):
    """故事内时间线的一条事件。

    顺序用显式 order_index，不解析 story_time：虚构历法与相对时间都没有
    可靠的字典序。story_time 只负责给人看。
    """

    __tablename__ = "timeline_event"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    story_time: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    order_index: Mapped[int] = mapped_column(Integer, default=0, index=True)
    participants_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    location_id: Mapped[str | None] = mapped_column(
        ForeignKey("setting_entry.id", ondelete="SET NULL"), default=None
    )
