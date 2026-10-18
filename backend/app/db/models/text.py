from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class SceneDraft(IdMixin, TimestampMixin, Base):
    """每个场景至多一条可编辑的 AI 草稿；不污染已采纳正文（D-04）。"""

    __tablename__ = "scene_draft"
    __table_args__ = (UniqueConstraint("scene_id", name="uq_scene_draft_scene"),)

    scene_id: Mapped[str] = mapped_column(
        ForeignKey("scene.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("generation_run.id", ondelete="SET NULL"), default=None
    )
    content: Mapped[str] = mapped_column(Text, default="")


class SceneRevision(IdMixin, TimestampMixin, Base):
    """不可变修订快照：ai（采纳）/ author（保存）/ restore（恢复）。"""

    __tablename__ = "scene_revision"

    scene_id: Mapped[str] = mapped_column(
        ForeignKey("scene.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(20), default="ai")
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("generation_run.id", ondelete="SET NULL"), default=None
    )
    note: Mapped[str] = mapped_column(Text, default="")
