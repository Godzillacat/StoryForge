from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class BatchJob(IdMixin, TimestampMixin, Base):
    """一次批量生成任务。进程内 worker 按 cursor 逐场推进，进度落库。

    只写 AI 草稿，永不写已采纳正文；已有正文或草稿的场景在创建与执行时跳过。
    """

    __tablename__ = "batch_job"
    __table_args__ = (
        Index("ix_batch_job_project_status", "project_id", "status"),
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    # chapter | volume
    scope_type: Mapped[str] = mapped_column(String(20))
    scope_id: Mapped[str] = mapped_column(String(36))
    # 有序场景 id；retry-failed 会把它重置为失败场景
    scene_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    cursor: Mapped[int] = mapped_column(Integer, default=0)
    # running | paused | completed | cancelled | failed
    status: Mapped[str] = mapped_column(String(20), default="paused")
    # [{scene_id, message}]
    failures_json: Mapped[list[dict]] = mapped_column(JSON, default=list)
