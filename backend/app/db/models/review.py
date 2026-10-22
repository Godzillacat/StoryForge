from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class ReviewMark(IdMixin, TimestampMixin, Base):
    """「待复核」标记：影响面分析发现的下游对象，作者还没重看过。

    `target_id` **不建外键** —— 它按 `target_type` 指向五种不同的表，一个外键
    指不了五处。代价是对象被删后标记不会自动消失，由各 delete 路径显式清理。
    """

    __tablename__ = "review_mark"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "target_type", "target_id", name="uq_review_mark_target"
        ),
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    # architecture | entry | volume | chapter | scene
    target_type: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[str] = mapped_column(String(36))
    reason: Mapped[str] = mapped_column(Text, default="")
