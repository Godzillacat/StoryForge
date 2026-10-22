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


class BranchRevision(IdMixin, TimestampMixin, Base):
    """分支正文的修订快照：不可变，来源 `author` / `ai`。

    与 `scene_revision` 分开：主版的修订历史回答「这个场景曾经是什么」，
    分支的修订历史回答「这条分支曾经是什么」，两者混在一张表里，作者在
    写作台看到的会是两条线交织。
    """

    __tablename__ = "branch_revision"

    branch_id: Mapped[str] = mapped_column(
        ForeignKey("scene_branch.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(20), default="author")
    note: Mapped[str] = mapped_column(Text, default="")
