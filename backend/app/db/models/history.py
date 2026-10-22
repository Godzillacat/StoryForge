from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class ChangeLog(IdMixin, TimestampMixin, Base):
    """按目标对象粒度的改动记录（产品 §4.11）。

    `target_id` **不建外键**：日志要比对象的命长。对象被删掉之后，
    作者仍该能在历史里看见「它曾经被改过、后来被删了」。
    """

    __tablename__ = "change_log"
    __table_args__ = (
        Index("ix_change_log_project_time", "project_id", "created_at"),
        Index(
            "ix_change_log_target",
            "project_id",
            "target_type",
            "target_id",
            "created_at",
        ),
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    # scene | chapter | volume | entry | architecture | snapshot | project
    target_type: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[str] = mapped_column(String(36))
    # **当时的**名称。对象后来改名或被删，这条记录仍要读得懂 —— 否则
    # 作者在历史里看到的是一串裸 UUID。
    target_label: Mapped[str] = mapped_column(String(200), default="")
    # create | update | delete | adopt | restore | rollback
    action: Mapped[str] = mapped_column(String(20))
    # author | ai | snapshot
    source: Mapped[str] = mapped_column(String(20), default="author")
    summary: Mapped[str] = mapped_column(Text, default="")
