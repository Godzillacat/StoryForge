from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class ProjectSnapshot(IdMixin, TimestampMixin, Base):
    """一份项目结构的完整快照，自包含、可独立删除。

    **存完整 JSON，不做增量。** 增量存储会让「删一份快照会不会影响另一份」
    变成需要推理的问题；一部百万字长篇的单份快照约几 MB，本机磁盘不是瓶颈。
    """

    __tablename__ = "project_snapshot"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_snapshot_project_name"),
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    note: Mapped[str] = mapped_column(Text, default="")
    data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # 规模冗余存一份：列表页只读这四列，不解析 JSON。
    volumes: Mapped[int] = mapped_column(Integer, default=0)
    chapters: Mapped[int] = mapped_column(Integer, default=0)
    scenes: Mapped[int] = mapped_column(Integer, default=0)
    words: Mapped[int] = mapped_column(Integer, default=0)
