from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class SceneBranch(IdMixin, TimestampMixin, Base):
    """一个场景的一条正文分支：同一场戏的另一种写法。

    场景卡（目标 / 冲突 / 转折 / 人物 / 地点）是**共享**的 —— 分支只是正文的
    并行实验，不是两场不同的戏。草稿直接挂在这一行上：每个分支至多一条，
    丢弃分支时草稿自然消失。
    """

    __tablename__ = "scene_branch"
    __table_args__ = (
        UniqueConstraint("scene_id", "name", name="uq_branch_scene_name"),
    )

    scene_id: Mapped[str] = mapped_column(
        ForeignKey("scene.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    content: Mapped[str] = mapped_column(Text, default="")
    draft_content: Mapped[str] = mapped_column(Text, default="")
    draft_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("generation_run.id", ondelete="SET NULL"), default=None
    )
    note: Mapped[str] = mapped_column(Text, default="")
